from app.core.introspect import introspect_model

EXPECTED_WITHOUT_GLUCOSE_RAW_INPUTS = [
    ("age", "continuous"),
    ("gender", "categorical"),
    ("pulse_rate", "continuous"),
    ("systolic_bp", "continuous"),
    ("diastolic_bp", "continuous"),
    ("height", "continuous"),
    ("weight", "continuous"),
    ("bmi", "continuous"),
    ("family_diabetes", "categorical"),
    ("hypertensive", "categorical"),
    ("family_hypertension", "categorical"),
    ("cardiovascular_disease", "categorical"),
    ("stroke", "categorical"),
]


def test_without_glucose_schema(without_glucose_model):
    schema = introspect_model(without_glucose_model, model_id="without")
    names = [(i.name, i.type) for i in schema.inputs]
    assert names == EXPECTED_WITHOUT_GLUCOSE_RAW_INPUTS
    assert schema.target.name == "diabetic"
    assert schema.target.values == ["No", "Yes"]
    gender = next(i for i in schema.inputs if i.name == "gender")
    assert gender.values == ["Female", "Male"]
    fd = next(i for i in schema.inputs if i.name == "family_diabetes")
    assert fd.values == ["0", "1"]
    assert schema.supports_contributions is True


def test_with_glucose_schema_has_glucose(with_glucose_model):
    schema = introspect_model(with_glucose_model, model_id="with")
    names = [i.name for i in schema.inputs]
    assert "glucose" in names
    assert len(names) == len(set(names)), "raw inputs should be unique"
    assert schema.target.name == "diabetic"
    assert schema.target.values == ["No", "Yes"]


def test_algorithm_is_recorded(without_glucose_model):
    schema = introspect_model(without_glucose_model, model_id="x")
    assert schema.algorithm
