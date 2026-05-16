from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.core.predict import PredictionInputError, predict
from app.schemas import PredictionResult, PredictRequest

router = APIRouter(prefix="/api/models", tags=["predict"])


@router.post("/{model_id}/predict", response_model=PredictionResult)
def run_prediction(model_id: str, body: PredictRequest, request: Request) -> PredictionResult:
    entry = request.app.state.registry.get(model_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Model {model_id!r} not found")
    try:
        return predict(entry.model, entry.schema, body.inputs)
    except PredictionInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
