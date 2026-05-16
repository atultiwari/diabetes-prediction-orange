"""Reconstruct a user-facing ModelSchema from an Orange classifier.

Orange's `Continuize` preprocessor one-hot expands every binary categorical
column into pairs named like `gender=Female`, `gender=Male`. After training,
`model.domain.attributes` contains the *expanded* columns, not the original
raw inputs the doctor saw in the workflow. We need to fold those expanded
columns back into the raw variables for the UI form.
"""

from __future__ import annotations

from app.schemas import InputSpec, ModelSchema, TargetSpec


def _split_expanded_name(attr_name: str) -> tuple[str, str | None]:
    """Return (raw_name, value_or_None).

    `gender=Female` -> ("gender", "Female")
    `age` -> ("age", None)
    """
    if "=" in attr_name:
        raw, value = attr_name.split("=", 1)
        return raw, value
    return attr_name, None


def _algorithm_name(model: object) -> str:
    return type(model).__name__


def _supports_contributions(model: object) -> bool:
    skl = getattr(model, "skl_model", None)
    if skl is None:
        return False
    return hasattr(skl, "coef_") or hasattr(skl, "feature_importances_")


def introspect_model(model: object, *, model_id: str, source: str = "bundled") -> ModelSchema:
    domain = model.domain  # type: ignore[attr-defined]

    raw_order: list[str] = []
    raw_kind: dict[str, str] = {}
    raw_values: dict[str, list[str]] = {}

    for attr in domain.attributes:
        attr_name = attr.name
        is_continuous_attr = getattr(attr, "is_continuous", False)
        raw_name, value = _split_expanded_name(attr_name)

        if value is not None:
            # Even if Orange marks it continuous (Discretize edge case),
            # the `name=value` shape means it's a categorical level.
            if raw_name not in raw_kind:
                raw_order.append(raw_name)
                raw_kind[raw_name] = "categorical"
                raw_values[raw_name] = []
            if value not in raw_values[raw_name]:
                raw_values[raw_name].append(value)
        else:
            if raw_name not in raw_kind:
                raw_order.append(raw_name)
                raw_kind[raw_name] = "continuous" if is_continuous_attr else "categorical"
            if not is_continuous_attr:
                values = list(getattr(attr, "values", []) or [])
                if values:
                    raw_values[raw_name] = values

    inputs: list[InputSpec] = []
    for name in raw_order:
        kind = raw_kind[name]
        if kind == "categorical":
            inputs.append(InputSpec(name=name, type="categorical", values=raw_values.get(name, [])))
        else:
            inputs.append(InputSpec(name=name, type="continuous"))

    class_var = domain.class_var
    target = TargetSpec(
        name=class_var.name,
        type="categorical" if getattr(class_var, "is_discrete", False) else "continuous",
        values=list(class_var.values) if getattr(class_var, "is_discrete", False) else None,
    )

    return ModelSchema(
        model_id=model_id,
        algorithm=_algorithm_name(model),
        target=target,
        inputs=inputs,
        supports_contributions=_supports_contributions(model),
        source=source,  # type: ignore[arg-type]
    )
