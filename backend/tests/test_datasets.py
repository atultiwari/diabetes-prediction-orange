import io
from pathlib import Path

import pytest

from app.core.datasets import (
    DatasetRegistry,
    is_compatible,
    open_csv_rows,
    run_batch,
    sample_row,
)
from app.core.introspect import introspect_model
from app.core.predict import predict_fast

BACKEND_ROOT = Path(__file__).resolve().parent.parent
DATASETS_DIR = BACKEND_ROOT / "datasets"


@pytest.fixture(scope="session")
def dataset_registry() -> DatasetRegistry:
    reg = DatasetRegistry(bundled_dir=DATASETS_DIR)
    reg.load_all()
    return reg


def test_registry_loads_both_datasets(dataset_registry: DatasetRegistry):
    ids = {e.dataset_id for e in dataset_registry.list_entries()}
    assert "DiaBD_A" in ids
    assert "DiaBD_without-BSL" in ids


def test_row_counts_skip_blank_rows(dataset_registry: DatasetRegistry):
    # The CSVs in this repo have blank rows interleaved with data; the loader
    # must not count them. ~5,288 real rows in each file.
    for entry in dataset_registry.list_entries():
        assert 4000 < entry.n_rows < 6000, f"{entry.dataset_id} reported {entry.n_rows} rows"


def test_compatibility_with_glucose(dataset_registry, with_glucose_model):
    schema = introspect_model(with_glucose_model, model_id="x")
    a = dataset_registry.get("DiaBD_A")
    bsl = dataset_registry.get("DiaBD_without-BSL")
    assert a is not None and bsl is not None
    assert is_compatible(a, schema) is True  # has glucose column
    assert is_compatible(bsl, schema) is False  # missing glucose


def test_compatibility_without_glucose(dataset_registry, without_glucose_model):
    schema = introspect_model(without_glucose_model, model_id="x")
    a = dataset_registry.get("DiaBD_A")
    bsl = dataset_registry.get("DiaBD_without-BSL")
    assert is_compatible(a, schema) is True  # superset of needed cols
    assert is_compatible(bsl, schema) is True


def test_list_schemas_assigns_compatible_models(
    dataset_registry, with_glucose_model, without_glucose_model
):
    schemas = [
        introspect_model(with_glucose_model, model_id="with"),
        introspect_model(without_glucose_model, model_id="without"),
    ]
    out = dataset_registry.list_schemas(schemas)
    by_id = {s.dataset_id: s for s in out}
    assert set(by_id["DiaBD_A"].compatible_model_ids) == {"with", "without"}
    assert by_id["DiaBD_without-BSL"].compatible_model_ids == ["without"]
    assert by_id["DiaBD_A"].target_column == "diabetic"


def test_sample_row_returns_usable_values(dataset_registry, without_glucose_model):
    schema = introspect_model(without_glucose_model, model_id="x")
    entry = dataset_registry.get("DiaBD_without-BSL")
    assert entry is not None
    result = sample_row(entry, schema, seed=42)
    # Every input the schema declares must be present in the sampled row
    assert set(result.inputs.keys()) == {inp.name for inp in schema.inputs}
    # Continuous values are floats, categorical are model-allowed strings
    for inp in schema.inputs:
        v = result.inputs[inp.name]
        if inp.type == "continuous":
            assert isinstance(v, float)
        else:
            assert v in (inp.values or [])
    assert result.true_class in {"No", "Yes"} or result.true_class is None


def test_sampled_row_is_actually_predictable(
    dataset_registry, without_glucose_model
):
    schema = introspect_model(without_glucose_model, model_id="x")
    entry = dataset_registry.get("DiaBD_without-BSL")
    assert entry is not None
    result = sample_row(entry, schema, seed=7)
    pred = predict_fast(without_glucose_model, schema, result.inputs)
    assert pred.predicted_class in {"No", "Yes"}


def test_run_batch_bundled(dataset_registry, without_glucose_model):
    schema = introspect_model(without_glucose_model, model_id="x")
    entry = dataset_registry.get("DiaBD_without-BSL")
    assert entry is not None

    rows = open_csv_rows(entry.path)
    result = run_batch(
        model=without_glucose_model,
        model_schema=schema,
        rows=rows,
        total_rows_hint=entry.n_rows,
        limit=50,
        source="bundled",
        dataset_id=entry.dataset_id,
        single_row_predict=predict_fast,
    )
    assert result.summary.rows_processed > 40  # accounting for some skips
    assert result.summary.rows_processed <= 50
    assert set(result.summary.predicted_class_counts.keys()) <= {"No", "Yes"}
    # True labels are in the CSV, so accuracy must be present
    assert result.summary.accuracy is not None
    assert 0.0 <= result.summary.accuracy <= 1.0
    assert result.rows_truncated is True


def test_run_batch_from_upload_string(dataset_registry, without_glucose_model):
    schema = introspect_model(without_glucose_model, model_id="x")
    entry = dataset_registry.get("DiaBD_without-BSL")
    # Use the bundled CSV bytes as a stand-in for an uploaded buffer.
    text = entry.path.read_text(encoding="utf-8-sig")
    rows = open_csv_rows(io.StringIO(text))
    result = run_batch(
        model=without_glucose_model,
        model_schema=schema,
        rows=rows,
        total_rows_hint=None,
        limit=None,  # process everything
        source="upload",
        dataset_id=None,
        single_row_predict=predict_fast,
    )
    # Without a limit we should process essentially every non-blank row.
    assert result.summary.rows_processed >= 4000
    assert result.summary.rows_processed <= entry.n_rows
    # Accuracy must round to something believable for a training-set replay.
    assert result.summary.accuracy is not None
    assert result.summary.accuracy > 0.5


def test_skipped_rows_reported(dataset_registry, without_glucose_model):
    schema = introspect_model(without_glucose_model, model_id="x")
    # Hand-craft a CSV with one good row + one bad row + one blank line.
    header = (
        "age,gender,pulse_rate,systolic_bp,diastolic_bp,height,weight,bmi,"
        "family_diabetes,hypertensive,family_hypertension,"
        "cardiovascular_disease,stroke,diabetic"
    )
    good = "30,Female,72,120,80,1.65,60,22,0,0,0,0,0,No"
    bad = "30,Nonbinary,72,120,80,1.65,60,22,0,0,0,0,0,No"
    blank = ",,,,,,,,,,,,,"
    csv_text = "\n".join([header, good, bad, blank, ""]) + "\n"
    rows = open_csv_rows(io.StringIO(csv_text))
    result = run_batch(
        model=without_glucose_model,
        model_schema=schema,
        rows=rows,
        total_rows_hint=None,
        limit=None,
        source="upload",
        dataset_id=None,
        single_row_predict=predict_fast,
    )
    assert result.summary.rows_processed == 1
    assert result.summary.rows_skipped == 1
    assert any("gender" in r for r in result.summary.skipped_reasons)
