"""Route-level integration tests for the new sample / batch / CSV endpoints."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture(scope="module")
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


def _without_id(client: TestClient) -> str:
    schemas = client.get("/api/models").json()
    return next(s["model_id"] for s in schemas if "without" in s["model_id"])


def _with_id(client: TestClient) -> str:
    schemas = client.get("/api/models").json()
    return next(s["model_id"] for s in schemas if "without" not in s["model_id"])


def test_list_datasets_endpoint(client: TestClient):
    r = client.get("/api/datasets")
    assert r.status_code == 200
    items = r.json()
    ids = {d["dataset_id"] for d in items}
    assert {"DiaBD_A", "DiaBD_without-BSL"} <= ids
    by_id = {d["dataset_id"]: d for d in items}
    # The full dataset should advertise both models as compatible
    assert len(by_id["DiaBD_A"]["compatible_model_ids"]) >= 2


def test_get_single_dataset(client: TestClient):
    r = client.get("/api/datasets/DiaBD_without-BSL")
    assert r.status_code == 200
    body = r.json()
    assert body["target_column"] == "diabetic"
    assert "glucose" not in body["columns"]


def test_sample_endpoint_returns_model_shaped_inputs(client: TestClient):
    model_id = _without_id(client)
    r = client.post(f"/api/models/{model_id}/sample", json={"seed": 1})
    assert r.status_code == 200
    body = r.json()
    assert body["dataset_id"] in {"DiaBD_A", "DiaBD_without-BSL"}
    schema = client.get(f"/api/models/{model_id}").json()
    expected = {inp["name"] for inp in schema["inputs"]}
    assert set(body["inputs"].keys()) == expected


def test_sample_with_explicit_dataset(client: TestClient):
    model_id = _without_id(client)
    r = client.post(
        f"/api/models/{model_id}/sample",
        json={"dataset_id": "DiaBD_without-BSL", "seed": 5},
    )
    assert r.status_code == 200
    assert r.json()["dataset_id"] == "DiaBD_without-BSL"


def test_sample_rejects_incompatible_dataset(client: TestClient):
    model_id = _with_id(client)
    # The without-glucose CSV is missing glucose — sample should fail for this
    # model because no row has the column it needs.
    r = client.post(
        f"/api/models/{model_id}/sample",
        json={"dataset_id": "DiaBD_without-BSL", "seed": 0},
    )
    assert r.status_code == 400


def test_batch_from_bundled(client: TestClient):
    model_id = _without_id(client)
    r = client.post(
        f"/api/models/{model_id}/predict/batch",
        json={"dataset_id": "DiaBD_without-BSL", "limit": 25, "seed": 1},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "bundled"
    assert body["summary"]["rows_processed"] <= 25
    assert body["summary"]["accuracy"] is not None
    assert len(body["rows"]) == body["summary"]["rows_processed"]
    assert body["rows_truncated"] is True


def test_batch_csv_download(client: TestClient):
    model_id = _without_id(client)
    r = client.get(
        f"/api/models/{model_id}/predict/batch.csv",
        params={"dataset_id": "DiaBD_without-BSL"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    body = r.text
    header = body.splitlines()[0]
    assert "predicted_class" in header
    assert "p_No" in header
    assert "p_Yes" in header
    # Make sure we actually streamed many rows
    assert len(body.splitlines()) > 100


def test_batch_upload_endpoint(client: TestClient):
    model_id = _without_id(client)
    schema = client.get(f"/api/models/{model_id}").json()
    inputs = [inp["name"] for inp in schema["inputs"]]
    header = ",".join(inputs + ["diabetic"])
    row1 = ",".join(
        ["30", "Female", "72", "120", "80", "1.65", "60", "22"] +
        ["0", "0", "0", "0", "0", "No"]
    )
    row2 = ",".join(
        ["65", "Male", "95", "165", "100", "1.70", "110", "38"] +
        ["1", "1", "1", "1", "1", "Yes"]
    )
    csv_text = "\n".join([header, row1, "", row2]) + "\n"

    r = client.post(
        f"/api/models/{model_id}/predict/batch-upload",
        files={"file": ("custom.csv", csv_text, "text/csv")},
        data={"limit": "10"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source"] == "upload"
    assert body["summary"]["rows_processed"] == 2
    assert body["rows"][0]["predicted_class"] in {"No", "Yes"}


def test_batch_upload_csv_download(client: TestClient):
    model_id = _without_id(client)
    schema = client.get(f"/api/models/{model_id}").json()
    inputs = [inp["name"] for inp in schema["inputs"]]
    header = ",".join(inputs + ["diabetic"])
    body_csv = "\n".join(
        [header]
        + [
            ",".join(
                ["30", "Female", "72", "120", "80", "1.65", "60", "22"] +
                ["0", "0", "0", "0", "0", "No"]
            )
            for _ in range(3)
        ]
    )
    r = client.post(
        f"/api/models/{model_id}/predict/batch-upload.csv",
        files={"file": ("upload.csv", body_csv, "text/csv")},
    )
    assert r.status_code == 200
    assert "predicted_class" in r.text.splitlines()[0]


def test_batch_rejects_empty_upload(client: TestClient):
    model_id = _without_id(client)
    r = client.post(
        f"/api/models/{model_id}/predict/batch-upload",
        files={"file": ("empty.csv", "", "text/csv")},
    )
    assert r.status_code == 400
