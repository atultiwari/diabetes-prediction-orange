"""Attribute a single prediction back to the raw (pre-one-hot) variables.

For Logistic Regression we have `skl_model.coef_` with shape
(1, n_expanded_features) for binary classification or (n_classes, ...) for
multi-class. The per-feature log-odds contribution is `coef * x_expanded`.
Those contributions are summed back into the raw variable they came from
(e.g. `gender=Female` and `gender=Male` both fold into `gender`).

For tree ensembles we fall back to `feature_importances_`, which has no sign
and no per-sample resolution — it's a global ranking, but it's the best
quick answer we can give without pulling in SHAP.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from app.core.introspect import _split_expanded_name  # internal helper reuse
from app.schemas import Contribution, ModelSchema

MAX_CONTRIBUTIONS = 5


def _expanded_row(model, table) -> np.ndarray | None:
    try:
        transformed = table.transform(model.domain)
        return np.asarray(transformed.X)[0]
    except Exception:  # noqa: BLE001 — defensive; some pipelines may not expose this cleanly
        return None


def _input_value_for(name: str, inputs_for_display: dict[str, Any]) -> Any:
    return inputs_for_display.get(name)


def _coef_row_for_class(coef: np.ndarray, predicted_idx: int) -> np.ndarray:
    if coef.ndim == 1:
        return coef
    if coef.shape[0] == 1:
        # Binary LR: coef points toward the positive class (index 1).
        return coef[0] if predicted_idx == 1 else -coef[0]
    return coef[predicted_idx]


def _logistic_contributions(
    model,
    schema: ModelSchema,
    table,
    predicted_label: str,
    inputs_for_display: dict[str, Any],
) -> list[Contribution]:
    skl = model.skl_model
    coef = np.asarray(skl.coef_)
    class_values = list(model.domain.class_var.values)
    predicted_idx = class_values.index(predicted_label)
    coef_row = _coef_row_for_class(coef, predicted_idx)

    x_expanded = _expanded_row(model, table)
    if x_expanded is None or x_expanded.shape[0] != coef_row.shape[0]:
        return []

    contributions_per_expanded = coef_row * x_expanded

    grouped: dict[str, float] = {}
    for attr, contribution in zip(model.domain.attributes, contributions_per_expanded):
        raw_name, _value = _split_expanded_name(attr.name)
        grouped[raw_name] = grouped.get(raw_name, 0.0) + float(contribution)

    ordered = sorted(grouped.items(), key=lambda kv: abs(kv[1]), reverse=True)
    return [
        Contribution(
            feature=name,
            input_value=_input_value_for(name, inputs_for_display),
            contribution=value,
        )
        for name, value in ordered[:MAX_CONTRIBUTIONS]
    ]


def _importance_contributions(
    model,
    schema: ModelSchema,
    inputs_for_display: dict[str, Any],
) -> list[Contribution]:
    skl = model.skl_model
    importances = np.asarray(skl.feature_importances_)

    grouped: dict[str, float] = {}
    for attr, imp in zip(model.domain.attributes, importances):
        raw_name, _value = _split_expanded_name(attr.name)
        grouped[raw_name] = grouped.get(raw_name, 0.0) + float(imp)

    ordered = sorted(grouped.items(), key=lambda kv: abs(kv[1]), reverse=True)
    return [
        Contribution(
            feature=name,
            input_value=_input_value_for(name, inputs_for_display),
            contribution=value,
        )
        for name, value in ordered[:MAX_CONTRIBUTIONS]
    ]


def compute_contributions(
    model,
    schema: ModelSchema,
    table,
    predicted_label: str,
    inputs_for_display: dict[str, Any],
) -> list[Contribution]:
    if not schema.supports_contributions:
        return []
    skl = getattr(model, "skl_model", None)
    if skl is None:
        return []
    if hasattr(skl, "coef_"):
        return _logistic_contributions(model, schema, table, predicted_label, inputs_for_display)
    if hasattr(skl, "feature_importances_"):
        return _importance_contributions(model, schema, inputs_for_display)
    return []
