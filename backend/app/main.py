"""FastAPI entrypoint.

CRITICAL: `QT_QPA_PLATFORM=offscreen` must be set before Orange is imported,
because the "with glucose" model unpickles Orange.widgets.utils.colorpalettes
which transitively touches AnyQt → PyQt5 → QPainter. Without an X server or
the offscreen platform plugin, the very first pickle.load crashes.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.datasets import DatasetRegistry
from app.core.registry import ModelRegistry
from app.routes import datasets as datasets_route
from app.routes import models as models_route
from app.routes import predict as predict_route

log = logging.getLogger("orange-demo")
logging.basicConfig(level=logging.INFO)

BACKEND_ROOT = Path(__file__).resolve().parent.parent
BUNDLED_DIR = Path(os.environ.get("BUNDLED_MODELS_DIR", BACKEND_ROOT / "models"))
UPLOADS_DIR = Path(os.environ.get("UPLOADS_DIR", BACKEND_ROOT / "uploads"))
DATASETS_DIR = Path(os.environ.get("DATASETS_DIR", BACKEND_ROOT / "datasets"))

FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000")
DEBUG = os.environ.get("DEBUG", "").lower() in {"1", "true", "yes"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    registry = ModelRegistry(bundled_dir=BUNDLED_DIR, uploads_dir=UPLOADS_DIR)
    log.info("Loading models from %s and %s", BUNDLED_DIR, UPLOADS_DIR)
    registry.load_all()
    loaded = [s.model_id for s in registry.list_schemas()]
    log.info("Loaded %d models: %s", len(loaded), loaded)
    app.state.registry = registry

    datasets = DatasetRegistry(bundled_dir=DATASETS_DIR)
    log.info("Loading datasets from %s", DATASETS_DIR)
    datasets.load_all()
    ds_ids = [e.dataset_id for e in datasets.list_entries()]
    log.info("Loaded %d datasets: %s", len(ds_ids), ds_ids)
    app.state.datasets = datasets

    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Orange Model Demo",
        version="0.1.0",
        lifespan=lifespan,
    )

    origins = [o.strip() for o in FRONTEND_ORIGIN.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(models_route.router)
    app.include_router(predict_route.router)
    app.include_router(datasets_route.router)

    if DEBUG:
        @app.post("/api/admin/reload")
        def reload_models(request_app: FastAPI = app) -> dict[str, list[str]]:  # type: ignore[assignment]
            request_app.state.registry.load_all()
            return {"models": [s.model_id for s in request_app.state.registry.list_schemas()]}

    return app


app = create_app()
