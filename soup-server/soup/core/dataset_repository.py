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

             Since commit 3 the files go through the "storage" tool
             (tool_storage package), one namespace per dataset: the
             namespace is the dataset name, so the folder stays
             /soup/<name>/ and existing volumes remain readable. The
             LOAD CSV paths come from storage.path_for(), the absolute
             path under the volume Memgraph reads from.
             TODO(commit 8): moves to the ekg package.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import json
from typing import Any

from soup.core.contracts import FileStorage, validate_name
from soup.core.services.legacy_tools import StorageSpaceTool


def _validate_name(name: str) -> str:
    """
    Dataset names become folder names: "", "..", separators and a leading
    "_" (reserved, e.g. for the catalog) are refused - the legacy code
    used dataset names directly in filesystem paths with no validation.
    """

    return validate_name(name, label="Dataset")


class DatasetRepository:
    def __init__(self, storage: StorageSpaceTool):
        self._storage = storage

    def _space(self, name: str) -> FileStorage:
        return self._storage.space(_validate_name(name))

    # ------------------------------------------------------------------ #
    # File names (layout - the one thing this class knows)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _events_csv(name: str) -> str:
        return f"{name}.csv"

    @staticmethod
    def _entities_csv(name: str) -> str:
        return f"{name}_entity.csv"

    @staticmethod
    def _config(name: str) -> str:
        return f"{name}_config.json"

    def events_csv_load_path(self, name: str) -> str:
        """Absolute in-container path for the events CSV, as used by LOAD CSV."""

        return self._storage.path_for(_validate_name(name), self._events_csv(name))

    def entities_csv_load_path(self, name: str) -> str:
        """Absolute in-container path for the entities CSV, as used by LOAD CSV."""

        return self._storage.path_for(_validate_name(name), self._entities_csv(name))

    # ------------------------------------------------------------------ #
    # Operations
    # ------------------------------------------------------------------ #
    def save_event_log(self, name: str, events_csv: bytes, entities_csv: bytes) -> None:
        space = self._space(name)
        space.write(self._events_csv(name), events_csv)
        space.write(self._entities_csv(name), entities_csv)

    def save_config(self, name: str, config: dict) -> None:
        """
        Persist `config` as-is (plus the schema's `source_format` field,
        already present in `config` by the time ImportService builds it)
        - any key this class does not know about is preserved verbatim,
        so older configs already on the volume stay readable.
        """

        payload = json.dumps(config, indent=4, ensure_ascii=False).encode("utf-8")
        self._space(name).write(self._config(name), payload)

    def load_config(self, name: str) -> dict[str, Any]:
        raw = self._space(name).read(self._config(name))
        return json.loads(raw.decode("utf-8"))

    def exists(self, name: str) -> bool:
        return self._space(name).exists(self._config(name))

    def delete(self, name: str) -> None:
        self._storage.delete_space(_validate_name(name))
