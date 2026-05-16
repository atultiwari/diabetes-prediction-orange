from __future__ import annotations

import csv
import io
from typing import Iterator

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse

from app.core.datasets import (
    DatasetError,
    DatasetRegistry,
    open_csv_rows,
    run_batch,
    sample_row,
)
from app.core.predict import PredictionInputError, predict, predict_fast
from app.core.registry import ModelEntry, ModelRegistry
from app.schemas import (
    BatchPredictionResult,
    BatchPredictRequest,
    PredictionResult,
    PredictRequest,
    SampleRowRequest,
    SampleRowResult,
)

router = APIRouter(prefix="/api/models", tags=["predict"])

MAX_BATCH_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB CSV upload cap
ABSOLUTE_MAX_ROWS = 10_000  # ceiling on how many rows we'll process per request


def _models(request: Request) -> ModelRegistry:
    return request.app.state.registry


def _datasets(request: Request) -> DatasetRegistry:
    return request.app.state.datasets


def _require_model(request: Request, model_id: str) -> ModelEntry:
    entry = _models(request).get(model_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Model {model_id!r} not found")
    return entry


@router.post("/{model_id}/predict", response_model=PredictionResult)
def run_prediction(
    model_id: str, body: PredictRequest, request: Request
) -> PredictionResult:
    entry = _require_model(request, model_id)
    try:
        return predict(entry.model, entry.schema, body.inputs)
    except PredictionInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{model_id}/sample", response_model=SampleRowResult)
def sample_for_model(
    model_id: str, body: SampleRowRequest, request: Request
) -> SampleRowResult:
    entry = _require_model(request, model_id)
    registry = _datasets(request)
    if body.dataset_id:
        ds = registry.get(body.dataset_id)
        if ds is None:
            raise HTTPException(status_code=404, detail=f"Dataset {body.dataset_id!r} not found")
    else:
        ds = registry.first_compatible_with(entry.schema)
        if ds is None:
            raise HTTPException(
                status_code=404,
                detail=f"No bundled dataset is compatible with {model_id!r}",
            )
    try:
        return sample_row(ds, entry.schema, seed=body.seed)
    except DatasetError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _clamp_limit(limit: int | None) -> int | None:
    if limit is None:
        return None
    if limit < 1:
        return 1
    return min(limit, ABSOLUTE_MAX_ROWS)


@router.post("/{model_id}/predict/batch", response_model=BatchPredictionResult)
def run_batch_from_dataset(
    model_id: str, body: BatchPredictRequest, request: Request
) -> BatchPredictionResult:
    entry = _require_model(request, model_id)
    ds = _datasets(request).get(body.dataset_id)
    if ds is None:
        raise HTTPException(status_code=404, detail=f"Dataset {body.dataset_id!r} not found")

    rows = open_csv_rows(ds.path)
    return run_batch(
        model=entry.model,
        model_schema=entry.schema,
        rows=rows,
        total_rows_hint=ds.n_rows,
        limit=_clamp_limit(body.limit),
        source="bundled",
        dataset_id=ds.dataset_id,
        single_row_predict=predict_fast,
    )


async def _read_upload(file: UploadFile) -> str:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty upload.")
    if len(data) > MAX_BATCH_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Upload exceeds {MAX_BATCH_UPLOAD_BYTES // (1024 * 1024)} MB limit.",
        )
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=400, detail=f"CSV must be UTF-8: {exc}"
        ) from exc


@router.post("/{model_id}/predict/batch-upload", response_model=BatchPredictionResult)
async def run_batch_from_upload(
    model_id: str,
    request: Request,
    file: UploadFile = File(...),
    limit: int | None = Form(default=50),
) -> BatchPredictionResult:
    entry = _require_model(request, model_id)
    text = await _read_upload(file)
    buffer = io.StringIO(text)
    rows = open_csv_rows(buffer)

    return run_batch(
        model=entry.model,
        model_schema=entry.schema,
        rows=rows,
        total_rows_hint=None,
        limit=_clamp_limit(limit),
        source="upload",
        dataset_id=None,
        single_row_predict=predict_fast,
    )


# ---- CSV streaming downloads ------------------------------------------------


def _stream_predictions_as_csv(
    *,
    model,
    schema,
    rows: Iterator[dict[str, str]],
) -> Iterator[str]:
    """Yield CSV chunks: original columns + predicted_class + p_<class> + correct."""
    class_values = list(schema.target.values or [])

    buffer = io.StringIO()
    writer = csv.writer(buffer)

    header = [inp.name for inp in schema.inputs]
    if schema.target.name:
        header.append(schema.target.name)
    header.append("predicted_class")
    header.extend(f"p_{c}" for c in class_values)
    header.append("correct")
    writer.writerow(header)
    yield buffer.getvalue()
    buffer.seek(0)
    buffer.truncate()

    from app.core.datasets import _coerce_row  # local import to avoid cycles

    for idx, raw in enumerate(rows):
        if idx >= ABSOLUTE_MAX_ROWS:
            break
        inputs, true_class, err = _coerce_row(raw, schema)
        if err is not None or inputs is None:
            continue
        try:
            result = predict_fast(model, schema, inputs)
        except Exception:  # noqa: BLE001 — skip bad row, keep streaming
            continue
        row_out = [str(inputs[i.name]) for i in schema.inputs]
        row_out.append(true_class if true_class is not None else "")
        row_out.append(result.predicted_class)
        for c in class_values:
            row_out.append(f"{result.probabilities.get(c, 0.0):.6f}")
        if true_class is not None:
            row_out.append("true" if true_class == result.predicted_class else "false")
        else:
            row_out.append("")
        writer.writerow(row_out)

        if buffer.tell() > 8192:
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate()

    if buffer.tell() > 0:
        yield buffer.getvalue()


@router.get("/{model_id}/predict/batch.csv")
def download_batch_csv(model_id: str, dataset_id: str, request: Request) -> StreamingResponse:
    entry = _require_model(request, model_id)
    ds = _datasets(request).get(dataset_id)
    if ds is None:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id!r} not found")

    iterator = _stream_predictions_as_csv(
        model=entry.model,
        schema=entry.schema,
        rows=open_csv_rows(ds.path),
    )
    filename = f"{model_id} on {dataset_id} - predictions.csv".replace("/", "-")
    return StreamingResponse(
        iterator,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.post("/{model_id}/predict/batch-upload.csv")
async def download_batch_csv_from_upload(
    model_id: str,
    request: Request,
    file: UploadFile = File(...),
) -> StreamingResponse:
    entry = _require_model(request, model_id)
    text = await _read_upload(file)
    buffer = io.StringIO(text)

    iterator = _stream_predictions_as_csv(
        model=entry.model,
        schema=entry.schema,
        rows=open_csv_rows(buffer),
    )
    safe_name = (file.filename or "upload.csv").rsplit(".", 1)[0]
    filename = f"{model_id} on {safe_name} - predictions.csv".replace("/", "-")
    return StreamingResponse(
        iterator,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
