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
