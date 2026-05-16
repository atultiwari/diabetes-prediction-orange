"""Bundled CSV datasets + batch-prediction helpers.

Each bundled CSV is associated with one or more models by column matching:
a dataset is "compatible" with a model when every raw input the model needs
has a same-named column in the CSV. The target column (if present) is also
detected by matching the model's class_var name.

The CSVs in `backend/datasets/` are committed to the repo and read-only at
runtime. We don't accept dataset *uploads* as persistent files — uploaded
CSVs for batch prediction are processed in-memory and discarded.
"""

from __future__ import annotations

import csv
import io
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from app.schemas import (
    BatchPredictionResult,
    BatchRowResult,
    BatchSummary,
    DatasetSchema,
    ModelSchema,
    SampleRowResult,
)

CSV_SUFFIX = ".csv"


@dataclass
class DatasetEntry:
    dataset_id: str
    filename: str
    path: Path
    columns: tuple[str, ...]
    n_rows: int  # non-empty data rows (header excluded)

    @property
    def column_set(self) -> frozenset[str]:
        return frozenset(self.columns)


class DatasetError(Exception):
    """Raised when a CSV is malformed or incompatible with the chosen model."""


def _row_is_empty(row: dict[str, str]) -> bool:
    return all((v is None or v.strip() == "") for v in row.values())


def _count_data_rows(path: Path) -> tuple[tuple[str, ...], int]:
    """Return (columns, count of non-empty data rows). Reads the whole file once."""
    with path.open("r", newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise DatasetError(f"{path.name}: no header row")
        columns = tuple(reader.fieldnames)
        count = sum(1 for row in reader if not _row_is_empty(row))
        return columns, count


class DatasetRegistry:
    def __init__(self, bundled_dir: Path):
        self.bundled_dir = bundled_dir
        self.bundled_dir.mkdir(parents=True, exist_ok=True)
        self._entries: dict[str, DatasetEntry] = {}

    def load_all(self) -> None:
        self._entries.clear()
        for path in sorted(self.bundled_dir.glob(f"*{CSV_SUFFIX}")):
            try:
                columns, n_rows = _count_data_rows(path)
            except Exception as exc:  # noqa: BLE001 — surface as a load error
                raise DatasetError(f"Failed to scan {path.name}: {exc}") from exc
            dataset_id = path.stem
            self._entries[dataset_id] = DatasetEntry(
                dataset_id=dataset_id,
                filename=path.name,
                path=path,
                columns=columns,
                n_rows=n_rows,
            )

    def list_entries(self) -> list[DatasetEntry]:
        return list(self._entries.values())

    def get(self, dataset_id: str) -> DatasetEntry | None:
        return self._entries.get(dataset_id)

    def list_schemas(self, model_schemas: list[ModelSchema]) -> list[DatasetSchema]:
        return [self._to_schema(e, model_schemas) for e in self._entries.values()]

    @staticmethod
    def _to_schema(entry: DatasetEntry, model_schemas: list[ModelSchema]) -> DatasetSchema:
        target_column: str | None = None
        compatible: list[str] = []
        for m in model_schemas:
            if is_compatible(entry, m):
                compatible.append(m.model_id)
                if m.target.name in entry.column_set:
                    target_column = m.target.name
        return DatasetSchema(
            dataset_id=entry.dataset_id,
            filename=entry.filename,
            n_rows=entry.n_rows,
            columns=list(entry.columns),
            target_column=target_column,
            compatible_model_ids=compatible,
        )

    def first_compatible_with(self, model_schema: ModelSchema) -> DatasetEntry | None:
        for entry in self._entries.values():
            if is_compatible(entry, model_schema):
                return entry
        return None


def is_compatible(entry: DatasetEntry, model_schema: ModelSchema) -> bool:
    """A dataset is compatible if every model input is present as a column."""
    needed = {inp.name for inp in model_schema.inputs}
    return needed.issubset(entry.column_set)


# ----- row coercion -----------------------------------------------------------


def _coerce_row(
    raw_row: dict[str, str],
    model_schema: ModelSchema,
) -> tuple[dict[str, object] | None, str | None, str | None]:
    """Return (inputs_for_model, true_class_or_None, error_or_None).

    inputs_for_model has values typed exactly the way Orange/predict.py expects:
    floats for continuous, exact-string for categorical.
    """
    inputs: dict[str, object] = {}
    for inp in model_schema.inputs:
        raw = raw_row.get(inp.name)
        if raw is None or raw == "":
            return None, None, f"missing value for {inp.name!r}"
        if inp.type == "continuous":
            try:
                inputs[inp.name] = float(raw)
            except ValueError:
                return None, None, f"non-numeric {inp.name}={raw!r}"
        else:
            text = str(raw).strip()
            # The trained domain stores categorical levels as strings even if
            # they look numeric — e.g. family_diabetes values are "0"/"1".
            # The CSV may write them as "0" or "0.0"; normalise the trailing
            # ".0" before checking against the model's declared values.
            if text.endswith(".0") and text[:-2].isdigit():
                text = text[:-2]
            if text not in (inp.values or []):
                return None, None, (
                    f"{inp.name}={raw!r} not in {list(inp.values or [])}"
                )
            inputs[inp.name] = text

    true_class: str | None = None
    target_name = model_schema.target.name
    raw_target = raw_row.get(target_name)
    if raw_target is not None and raw_target != "":
        candidate = str(raw_target).strip()
        if candidate.endswith(".0") and candidate[:-2].isdigit():
            candidate = candidate[:-2]
        if candidate in (model_schema.target.values or []):
            true_class = candidate

    return inputs, true_class, None


# ----- public helpers --------------------------------------------------------


def open_csv_rows(source: Path | str | io.StringIO) -> Iterator[dict[str, str]]:
    """Yield non-empty rows from a CSV file or in-memory string."""
    if isinstance(source, Path):
        fh = source.open("r", newline="", encoding="utf-8-sig")
        close = True
    elif isinstance(source, io.StringIO):
        fh = source
        close = False
    else:
        fh = io.StringIO(source)
        close = False

    try:
        reader = csv.DictReader(fh)
        for row in reader:
            if _row_is_empty(row):
                continue
            yield {k: ("" if v is None else v) for k, v in row.items()}
    finally:
        if close:
            fh.close()


def sample_row(
    entry: DatasetEntry,
    model_schema: ModelSchema,
    seed: int | None = None,
) -> SampleRowResult:
    rng = random.Random(seed)
    candidates: list[tuple[int, dict[str, object], str | None]] = []

    for idx, raw in enumerate(open_csv_rows(entry.path)):
        inputs, true_class, err = _coerce_row(raw, model_schema)
        if err is not None:
            continue
        assert inputs is not None
        candidates.append((idx, inputs, true_class))
        if len(candidates) >= 256:  # reservoir cap — plenty of variety
            break

    if not candidates:
        raise DatasetError(
            f"No usable rows in {entry.filename} for model {model_schema.model_id!r}"
        )

    idx, inputs, true_class = rng.choice(candidates)
    return SampleRowResult(
        dataset_id=entry.dataset_id,
        row_index=idx,
        inputs=inputs,
        true_class=true_class,
    )


def _confusion_matrix(
    classes: list[str], pairs: list[tuple[str, str]]
) -> dict[str, dict[str, int]]:
    matrix: dict[str, dict[str, int]] = {
        true: {pred: 0 for pred in classes} for true in classes
    }
    for true, pred in pairs:
        if true in matrix and pred in matrix[true]:
            matrix[true][pred] += 1
    return matrix


def run_batch(
    *,
    model,
    model_schema: ModelSchema,
    rows: Iterator[dict[str, str]],
    total_rows_hint: int | None,
    limit: int | None,
    source: str,
    dataset_id: str | None,
    single_row_predict,
) -> BatchPredictionResult:
    """Run prediction over every row, return a BatchPredictionResult.

    `single_row_predict(model, schema, inputs) -> PredictionResult` is injected
    so this module doesn't need to know about Orange — keeps the unit boundary
    clean for tests.
    """
    processed = 0
    skipped = 0
    skip_reasons: list[str] = []
    out_rows: list[BatchRowResult] = []
    pred_counts: dict[str, int] = {}
    prob_sums: dict[str, float] = {}
    true_pairs: list[tuple[str, str]] = []

    rows_truncated = False

    for idx, raw in enumerate(rows):
        if limit is not None and processed >= limit:
            rows_truncated = True
            break

        inputs, true_class, err = _coerce_row(raw, model_schema)
        if err is not None:
            skipped += 1
            if len(skip_reasons) < 10:
                skip_reasons.append(f"row {idx}: {err}")
            continue
        assert inputs is not None

        try:
            result = single_row_predict(model, model_schema, inputs)
        except Exception as exc:  # noqa: BLE001 — surface, don't abort the batch
            skipped += 1
            if len(skip_reasons) < 10:
                skip_reasons.append(f"row {idx}: predict failed — {exc}")
            continue

        processed += 1
        pred_counts[result.predicted_class] = pred_counts.get(result.predicted_class, 0) + 1
        for cls, p in result.probabilities.items():
            prob_sums[cls] = prob_sums.get(cls, 0.0) + p
        correct: bool | None = None
        if true_class is not None:
            correct = (true_class == result.predicted_class)
            true_pairs.append((true_class, result.predicted_class))

        out_rows.append(
            BatchRowResult(
                row_index=idx,
                inputs=inputs,
                predicted_class=result.predicted_class,
                probabilities=result.probabilities,
                true_class=true_class,
                correct=correct,
            )
        )

    avg_probs = {cls: (s / processed) for cls, s in prob_sums.items()} if processed else {}
    accuracy: float | None = None
    confusion: dict[str, dict[str, int]] | None = None
    if true_pairs:
        correct_count = sum(1 for t, p in true_pairs if t == p)
        accuracy = correct_count / len(true_pairs)
        confusion = _confusion_matrix(list(model_schema.target.values or []), true_pairs)

    summary = BatchSummary(
        total_rows_in_source=total_rows_hint if total_rows_hint is not None else processed + skipped,
        rows_processed=processed,
        rows_skipped=skipped,
        skipped_reasons=skip_reasons,
        predicted_class_counts=pred_counts,
        average_probabilities=avg_probs,
        accuracy=accuracy,
        confusion_matrix=confusion,
    )

    return BatchPredictionResult(
        model_id=model_schema.model_id,
        source=source,  # type: ignore[arg-type]
        dataset_id=dataset_id,
        summary=summary,
        rows=out_rows,
        rows_truncated=rows_truncated,
    )
