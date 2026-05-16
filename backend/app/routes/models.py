from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status

from app.core.registry import ModelLoadError, ModelRegistry
from app.schemas import ModelSchema

MAX_UPLOAD_BYTES = 50 * 1024 * 1024

router = APIRouter(prefix="/api/models", tags=["models"])


def _registry(request: Request) -> ModelRegistry:
    return request.app.state.registry


@router.get("", response_model=list[ModelSchema])
def list_models(request: Request) -> list[ModelSchema]:
    return _registry(request).list_schemas()


@router.get("/{model_id}", response_model=ModelSchema)
def get_model(model_id: str, request: Request) -> ModelSchema:
    entry = _registry(request).get(model_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Model {model_id!r} not found")
    return entry.schema


@router.post("", response_model=ModelSchema, status_code=status.HTTP_201_CREATED)
async def upload_model(request: Request, file: UploadFile = File(...)) -> ModelSchema:
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Upload exceeds 50 MB limit.")
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Empty file.")
    try:
        entry = _registry(request).add_upload(file.filename or "model.pkcls", data)
    except ModelLoadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return entry.schema


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_model(model_id: str, request: Request) -> None:
    registry = _registry(request)
    entry = registry.get(model_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Model {model_id!r} not found")
    if entry.source == "bundled":
        raise HTTPException(status_code=403, detail="Bundled models cannot be deleted.")
    try:
        registry.delete_upload(model_id)
    except ModelLoadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
