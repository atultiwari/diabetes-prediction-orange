import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pickle
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = BACKEND_ROOT / "models"

WITH_GLUCOSE = MODELS_DIR / "DM2 with glucose workflo.pkcls"
WITHOUT_GLUCOSE = MODELS_DIR / "DM2 without glucose workflo.pkcls"


@pytest.fixture(scope="session")
def with_glucose_model():
    with WITH_GLUCOSE.open("rb") as fh:
        return pickle.load(fh)


@pytest.fixture(scope="session")
def without_glucose_model():
    with WITHOUT_GLUCOSE.open("rb") as fh:
        return pickle.load(fh)
