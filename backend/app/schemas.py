from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

InputType = Literal["continuous", "categorical"]


class TargetSpec(BaseModel):
    name: str
    type: InputType
    values: list[str] | None = None


class InputSpec(BaseModel):
    name: str
    type: InputType
    values: list[str] | None = None


class ModelSchema(BaseModel):
    model_id: str
    algorithm: str
    target: TargetSpec
    inputs: list[InputSpec]
    supports_contributions: bool
    source: Literal["bundled", "uploaded"] = "bundled"


class PredictRequest(BaseModel):
    inputs: dict[str, Any]


class Contribution(BaseModel):
    feature: str
    input_value: Any
    contribution: float


class PredictionResult(BaseModel):
    predicted_class: str
    probabilities: dict[str, float]
    contributions: list[Contribution] = Field(default_factory=list)


# ---- datasets / sample / batch ----------------------------------------------


class DatasetSchema(BaseModel):
    dataset_id: str
    filename: str
    n_rows: int
    columns: list[str]
    target_column: str | None
    compatible_model_ids: list[str]


class SampleRowRequest(BaseModel):
    dataset_id: str | None = None
    seed: int | None = None


class SampleRowResult(BaseModel):
    dataset_id: str
    row_index: int
    inputs: dict[str, Any]
    true_class: str | None


class BatchPredictRequest(BaseModel):
    dataset_id: str
    limit: int | None = 50
    seed: int | None = None


class BatchRowResult(BaseModel):
    row_index: int
    inputs: dict[str, Any]
    predicted_class: str
    probabilities: dict[str, float]
    true_class: str | None = None
    correct: bool | None = None


class BatchSummary(BaseModel):
    total_rows_in_source: int
    rows_processed: int
    rows_skipped: int
    skipped_reasons: list[str] = Field(default_factory=list)
    predicted_class_counts: dict[str, int] = Field(default_factory=dict)
    average_probabilities: dict[str, float] = Field(default_factory=dict)
    accuracy: float | None = None
    confusion_matrix: dict[str, dict[str, int]] | None = None


class BatchPredictionResult(BaseModel):
    model_id: str
    source: Literal["bundled", "upload"]
    dataset_id: str | None
    summary: BatchSummary
    rows: list[BatchRowResult]
    rows_truncated: bool
