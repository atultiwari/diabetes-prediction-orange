import pytest

from app.core.introspect import introspect_model
from app.core.predict import PredictionInputError, predict


def _healthy_inputs_without_glucose():
    return {
        "age": 30,
        "gender": "Female",
        "pulse_rate": 72,
        "systolic_bp": 120,
        "diastolic_bp": 80,
        "height": 165,
        "weight": 60,
        "bmi": 22.0,
        "family_diabetes": "0",
        "hypertensive": "0",
        "family_hypertension": "0",
        "cardiovascular_disease": "0",
        "stroke": "0",
    }


def _high_risk_inputs_without_glucose():
    return {
        "age": 65,
        "gender": "Male",
        "pulse_rate": 95,
        "systolic_bp": 165,
        "diastolic_bp": 100,
        "height": 170,
        "weight": 110,
        "bmi": 38.0,
        "family_diabetes": "1",
        "hypertensive": "1",
        "family_hypertension": "1",
        "cardiovascular_disease": "1",
        "stroke": "1",
    }


def test_predict_returns_valid_probabilities(without_glucose_model):
    schema = introspect_model(without_glucose_model, model_id="x")
    result = predict(without_glucose_model, schema, _healthy_inputs_without_glucose())

    assert result.predicted_class in {"No", "Yes"}
    assert set(result.probabilities.keys()) == {"No", "Yes"}
    assert sum(result.probabilities.values()) == pytest.approx(1.0, abs=1e-6)
    for v in result.probabilities.values():
        assert 0.0 <= v <= 1.0


def test_predict_contributions_for_lr(without_glucose_model):
    schema = introspect_model(without_glucose_model, model_id="x")
    result = predict(without_glucose_model, schema, _high_risk_inputs_without_glucose())
    assert len(result.contributions) > 0
    assert len(result.contributions) <= 5
    raw_names = {i.name for i in schema.inputs}
    for c in result.contributions:
        assert c.feature in raw_names


def test_predict_high_risk_differs_from_low_risk(without_glucose_model):
    schema = introspect_model(without_glucose_model, model_id="x")
    low = predict(without_glucose_model, schema, _healthy_inputs_without_glucose())
    high = predict(without_glucose_model, schema, _high_risk_inputs_without_glucose())
    # Whatever the prediction labels are, a 25-year gap + obesity + comorbidities
    # should move probability of Yes upward.
    assert high.probabilities["Yes"] > low.probabilities["Yes"]


def test_predict_rejects_missing_field(without_glucose_model):
    schema = introspect_model(without_glucose_model, model_id="x")
    inputs = _healthy_inputs_without_glucose()
    del inputs["age"]
    with pytest.raises(PredictionInputError):
        predict(without_glucose_model, schema, inputs)


def test_predict_rejects_bad_categorical(without_glucose_model):
    schema = introspect_model(without_glucose_model, model_id="x")
    inputs = _healthy_inputs_without_glucose()
    inputs["gender"] = "Nonbinary"
    with pytest.raises(PredictionInputError):
        predict(without_glucose_model, schema, inputs)


def test_predict_rejects_non_numeric_continuous(without_glucose_model):
    schema = introspect_model(without_glucose_model, model_id="x")
    inputs = _healthy_inputs_without_glucose()
    inputs["age"] = "notanumber"
    with pytest.raises(PredictionInputError):
        predict(without_glucose_model, schema, inputs)


def test_with_glucose_model_loads_and_predicts(with_glucose_model):
    schema = introspect_model(with_glucose_model, model_id="x")
    raw = {}
    for inp in schema.inputs:
        if inp.type == "continuous":
            raw[inp.name] = 1.0
        else:
            raw[inp.name] = (inp.values or ["0"])[0]
    result = predict(with_glucose_model, schema, raw)
    assert result.predicted_class in set(schema.target.values or [])
