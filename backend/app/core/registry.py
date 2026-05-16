"""In-memory cache of loaded Orange models.

Pickle loading of `.pkcls` is slow (it pulls in Orange + Qt) so we cache by
filename. The registry knows which models are bundled (read-only) vs uploaded
(deletable) by which folder they live in.
"""

from __future__ import annotations

import pickle
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.core.introspect import introspect_model
from app.schemas import ModelSchema

ModelSource = Literal["bundled", "uploaded"]
PKCLS_SUFFIX = ".pkcls"
SAFE_FILENAME_RE = re.compile(r"^[A-Za-z0-9._\- ]+$")


@dataclass
class ModelEntry:
    model_id: str
    path: Path
    source: ModelSource
    model: object
    schema: ModelSchema


class ModelLoadError(Exception):
    """Raised when a .pkcls file cannot be loaded or is not an Orange classifier."""


class ModelRegistry:
    def __init__(self, bundled_dir: Path, uploads_dir: Path):
        self.bundled_dir = bundled_dir
        self.uploads_dir = uploads_dir
        self.bundled_dir.mkdir(parents=True, exist_ok=True)
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self._entries: dict[str, ModelEntry] = {}
        self._lock = threading.Lock()

    @staticmethod
    def model_id_from_path(path: Path) -> str:
        return path.stem

    def load_all(self) -> None:
        with self._lock:
            self._entries.clear()
            for path in sorted(self.bundled_dir.glob(f"*{PKCLS_SUFFIX}")):
                self._load_one(path, "bundled")
            for path in sorted(self.uploads_dir.glob(f"*{PKCLS_SUFFIX}")):
                self._load_one(path, "uploaded")

    def _load_one(self, path: Path, source: ModelSource) -> ModelEntry:
        model_id = self.model_id_from_path(path)
        try:
            with path.open("rb") as fh:
                model = pickle.load(fh)
        except Exception as exc:  # noqa: BLE001 — pickle can raise anything
            raise ModelLoadError(f"Failed to unpickle {path.name}: {exc}") from exc

        if not (hasattr(model, "domain") and getattr(model.domain, "class_var", None) is not None):
            raise ModelLoadError(
                f"{path.name} does not look like an Orange classifier "
                "(missing .domain or .domain.class_var)."
            )

        schema = introspect_model(model, model_id=model_id, source=source)
        entry = ModelEntry(model_id=model_id, path=path, source=source, model=model, schema=schema)
        self._entries[model_id] = entry
        return entry

    def list_schemas(self) -> list[ModelSchema]:
        with self._lock:
            return [entry.schema for entry in self._entries.values()]

    def get(self, model_id: str) -> ModelEntry | None:
        with self._lock:
            return self._entries.get(model_id)

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        name = Path(filename).name
        if not name.endswith(PKCLS_SUFFIX):
            raise ModelLoadError("Filename must end in .pkcls")
        if not SAFE_FILENAME_RE.match(name):
            raise ModelLoadError(
                "Filename may only contain letters, digits, dot, underscore, hyphen, space."
            )
        if ".." in name or name.startswith("."):
            raise ModelLoadError("Invalid filename.")
        return name

    def add_upload(self, filename: str, data: bytes) -> ModelEntry:
        with self._lock:
            safe_name = self.sanitize_filename(filename)
            model_id = Path(safe_name).stem

            bundled_path = self.bundled_dir / safe_name
            if bundled_path.exists():
                raise ModelLoadError(
                    f"A bundled model named {safe_name!r} already exists. Choose another name."
                )
            if model_id in self._entries and self._entries[model_id].source == "bundled":
                raise ModelLoadError(
                    f"Model id {model_id!r} collides with a bundled model. Rename your file."
                )

            target_path = self.uploads_dir / safe_name
            target_path.write_bytes(data)
            try:
                return self._load_one(target_path, "uploaded")
            except ModelLoadError:
                target_path.unlink(missing_ok=True)
                raise

    def delete_upload(self, model_id: str) -> None:
        with self._lock:
            entry = self._entries.get(model_id)
            if entry is None:
                raise ModelLoadError(f"Unknown model {model_id!r}.")
            if entry.source != "uploaded":
                raise ModelLoadError("Bundled models cannot be deleted.")
            entry.path.unlink(missing_ok=True)
            del self._entries[model_id]
