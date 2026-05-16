"""Run an Orange model against a raw-input row coming from the UI form.

Orange's `Continuize` is bound into the classifier as part of its domain
transform chain. That means we build a Table in the raw (pre-expansion)
domain we reconstructed for the form, hand it to `model(...)`, and Orange
applies the same one-hot expansion it learned during training.
"""

from __future__ import annotations

from typing import Any

import Orange
import numpy as np
from Orange.data import ContinuousVariable, DiscreteVariable, Domain, Table

from app.core.contributions import compute_contributions
from app.schemas import InputSpec, ModelSchema, PredictionResult


class PredictionInputError(ValueError):
    """Raised on bad user input (bad numeric value, unknown categorical, missing field)."""


def _coerce_value(spec: InputSpec, value: Any) -> Any:
    if value is None or (isinstance(value, str) and value.strip() == ""):
        raise PredictionInputError(f"Missing value for {spec.name!r}")
    if spec.type == "continuous":
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise PredictionInputError(
                f"{spec.name!r} must be a number, got {value!r}"
            ) from exc
    text = str(value)
    allowed = spec.values or []
    if text not in allowed:
        raise PredictionInputError(
            f"{spec.name!r} must be one of {allowed}, got {value!r}"
        )
    return text


def _build_raw_domain(schema: ModelSchema, class_var) -> Domain:
    attrs: list[Any] = []
    for inp in schema.inputs:
        if inp.type == "continuous":
            attrs.append(ContinuousVariable(inp.name))
        else:
            attrs.append(DiscreteVariable(inp.name, values=list(inp.values or [])))
    return Domain(attrs, class_vars=[class_var])


def predict(model, schema: ModelSchema, raw_inputs: dict[str, Any]) -> PredictionResult:
    coerced_row: list[Any] = []
    coerced_for_display: dict[str, Any] = {}
    for inp in schema.inputs:
        if inp.name not in raw_inputs:
            raise PredictionInputError(f"Missing value for {inp.name!r}")
        value = _coerce_value(inp, raw_inputs[inp.name])
        coerced_for_display[inp.name] = value
        coerced_row.append(value)

    class_var = model.domain.class_var
    raw_domain = _build_raw_domain(schema, class_var)
    table = Table.from_list(raw_domain, [coerced_row + [None]])

    pred_idx, probs = model(table, model.ValueProbs)
    class_values = list(class_var.values)
    predicted_label = class_values[int(np.asarray(pred_idx).reshape(-1)[0])]
    prob_row = np.asarray(probs)[0]
    probabilities = {name: float(prob_row[i]) for i, name in enumerate(class_values)}

    contributions = compute_contributions(
        model=model,
        schema=schema,
        table=table,
        predicted_label=predicted_label,
        inputs_for_display=coerced_for_display,
    )

    return PredictionResult(
        predicted_class=predicted_label,
        probabilities=probabilities,
        contributions=contributions,
    )
