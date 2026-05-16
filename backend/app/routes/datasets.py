from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.core.datasets import DatasetRegistry
from app.core.registry import ModelRegistry
from app.schemas import DatasetSchema

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


def _datasets(request: Request) -> DatasetRegistry:
    return request.app.state.datasets


def _models(request: Request) -> ModelRegistry:
    return request.app.state.registry


@router.get("", response_model=list[DatasetSchema])
def list_datasets(request: Request) -> list[DatasetSchema]:
    return _datasets(request).list_schemas(_models(request).list_schemas())


@router.get("/{dataset_id}", response_model=DatasetSchema)
def get_dataset(dataset_id: str, request: Request) -> DatasetSchema:
    entry = _datasets(request).get(dataset_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id!r} not found")
    schemas = _models(request).list_schemas()
    return _datasets(request)._to_schema(entry, schemas)
