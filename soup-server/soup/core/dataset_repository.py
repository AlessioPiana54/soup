"""
------------------------------------------------------------------------
File : dataset_repository.py
Description: DatasetRepository - the only place that knows the dataset
             volume layout. Layout reproduced byte-for-byte from the
             legacy code (not modified by this session):
             Models/file_manager_model.py (local temp staging),
             Models/docker_file_manager_model.py (container paths) and
             Services/dataset_service.py (folder-per-dataset under
             /soup). For a dataset named <name>:

                 /soup/<name>/<name>.csv            events CSV
                 /soup/<name>/<name>_entity.csv      entities CSV
                 /soup/<name>/<name>_config.json     config
                 /soup/<name>/<name>_config.svg      svg (not written here)

             Reads/writes go through the FileStorage port (so the actual
             backend - Docker volume, local filesystem, in-memory fake -
             is irrelevant to this class); the LOAD CSV path methods
             return the fixed in-container path under `root` (default
             "/soup") regardless of which FileStorage backend is wired up,
             because Memgraph always reads from the volume mounted at
             that path, not through our FileStorage abstraction.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import json
import re
from typing import Any

from soup.core.contracts import FileStorage
from soup.core.contracts.errors import ValidationError

_INVALID_NAME_CHARS = re.compile(r"[\\/]")


def _validate_name(name: str, *, label: str = "Dataset") -> str:
    """
    Reject "", ".", "..", path separators and any directory-traversal
    attempt - the legacy code used dataset/analysis names directly in
    filesystem paths with no validation at all.
    """

    if not isinstance(name, str) or name == "":
        raise ValidationError(f"{label} name must not be empty")
    if name in (".", ".."):
        raise ValidationError(f"Invalid {label.lower()} name: {name!r}")
    if _INVALID_NAME_CHARS.search(name):
        raise ValidationError(f"{label} name must not contain path separators: {name!r}")
    if ".." in name:
        raise ValidationError(f"{label} name must not contain '..': {name!r}")
    return name


class DatasetRepository:
    def __init__(self, storage: FileStorage, root: str = "/soup"):
        self._storage = storage
        self._root = root.rstrip("/") or "/"

    # ------------------------------------------------------------------ #
    # Paths (layout - the one thing this class knows)
    # ------------------------------------------------------------------ #
    def _dataset_dir(self, name: str) -> str:
        return f"{name}/"

    def _events_csv_path(self, name: str) -> str:
        return f"{name}/{name}.csv"

    def _entities_csv_path(self, name: str) -> str:
        return f"{name}/{name}_entity.csv"

    def _config_path(self, name: str) -> str:
        return f"{name}/{name}_config.json"

    def events_csv_load_path(self, name: str) -> str:
        """Absolute in-container path for the events CSV, as used by LOAD CSV."""

        _validate_name(name)
        return f"{self._root}/{name}/{name}.csv"

    def entities_csv_load_path(self, name: str) -> str:
        """Absolute in-container path for the entities CSV, as used by LOAD CSV."""

        _validate_name(name)
        return f"{self._root}/{name}/{name}_entity.csv"

    # ------------------------------------------------------------------ #
    # Operations
    # ------------------------------------------------------------------ #
    def save_event_log(self, name: str, events_csv: bytes, entities_csv: bytes) -> None:
        _validate_name(name)
        self._storage.write(self._events_csv_path(name), events_csv)
        self._storage.write(self._entities_csv_path(name), entities_csv)

    def save_config(self, name: str, config: dict) -> None:
        """
        Persist `config` as-is (plus the schema's `source_format` field,
        already present in `config` by the time ImportService builds it)
        - any key this class does not know about is preserved verbatim,
        so older configs already on the volume stay readable.
        """

        _validate_name(name)
        payload = json.dumps(config, indent=4, ensure_ascii=False).encode("utf-8")
        self._storage.write(self._config_path(name), payload)

    def load_config(self, name: str) -> dict[str, Any]:
        _validate_name(name)
        raw = self._storage.read(self._config_path(name))
        return json.loads(raw.decode("utf-8"))

    def exists(self, name: str) -> bool:
        _validate_name(name)
        return self._storage.exists(self._config_path(name))

    def delete(self, name: str) -> None:
        _validate_name(name)
        prefix = self._dataset_dir(name)
        for path in self._storage.list(prefix):
            self._storage.delete(path)
        # Directory-aware adapters (local filesystem, Docker volume) treat
        # the bare dataset name as the whole directory; a no-op for
        # key-value fakes where no such key was ever written.
        self._storage.delete(name)
