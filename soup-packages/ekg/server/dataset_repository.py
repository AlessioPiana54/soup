"""
------------------------------------------------------------------------
File : dataset_repository.py
Description: DatasetRepository - the only place that knows the dataset
             volume layout (moved here from soup/core). Layout reproduced
             byte-for-byte from the legacy code:
             Models/file_manager_model.py (local temp staging),
             Models/docker_file_manager_model.py (container paths),
             Services/dataset_service.py (folder-per-dataset under /soup)
             and Services/filters_service.py (analyses). For a dataset
             named <name>:

                 /soup/<name>/<name>.csv            events CSV
                 /soup/<name>/<name>_entity.csv      entities CSV
                 /soup/<name>/<name>_config.json     config
                 /soup/<name>/<name>_config.svg      svg (not written here)
                 /soup/<name>/Analyses/              the saved analyses

             The files go through the "storage" tool (tool_storage
             package), one namespace per dataset: the namespace is the
             dataset name, so the folder stays /soup/<name>/ and existing
             volumes remain readable. The LOAD CSV paths come from
             storage.path_for(), the absolute path under the volume
             Memgraph reads from.
Project : soup-packages/ekg
------------------------------------------------------------------------
"""

from __future__ import annotations

import json
from typing import Any, Protocol

from soup.core.contracts import FileStorage, ValidationError, validate_name

ANALYSES_FOLDER = "Analyses"


class StorageSpaceTool(Protocol):
    """What the repository uses of the "storage" tool (tool_storage's StorageTool)."""

    def space(self, namespace: str) -> Any:
        ...

    def path_for(self, namespace: str, name: str) -> str:
        ...

    def delete_space(self, namespace: str) -> None:
        ...

    def namespaces(self) -> list[str]:
        ...


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
        already present in `config` by the time build_ekg builds it)
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
        """Remove the whole /soup/<name>/ folder, Analyses/ included."""

        self._storage.delete_space(_validate_name(name))

    def datasets(self) -> list[str]:
        """The folders under the root holding a <name>/<name>_config.json, by name."""

        names = []
        for name in self._storage.namespaces():
            try:
                if self.exists(name):
                    names.append(name)
            except ValidationError:
                continue  # not a dataset folder name (e.g. a file at the root)
        return sorted(names)

    def free_name(self, wanted: str) -> str:
        """`wanted`, or `wanted_2`, `wanted_3`... - the first one with no dataset folder yet."""

        _validate_name(wanted)
        taken = set(self._storage.namespaces())
        name, suffix = wanted, 2
        while name in taken:
            name, suffix = _validate_name(f"{wanted[:120]}_{suffix}"), suffix + 1
        return name

    # ------------------------------------------------------------------ #
    # Analyses (/soup/<name>/Analyses/<analysis>.json)
    # ------------------------------------------------------------------ #
    def _analyses(self, name: str) -> FileStorage:
        return self._space(name).subspace(ANALYSES_FOLDER)

    def analyses(self, name: str) -> list[str]:
        """The names of the analyses saved for the dataset (without .json)."""

        return [file[:-len(".json")] for file in self._analyses(name).list() if file.endswith(".json")]

    def save_analysis(self, name: str, analysis: str, data: dict) -> None:
        payload = json.dumps(data, indent=4, ensure_ascii=False).encode("utf-8")
        self._analyses(name).write(f"{validate_name(analysis, label='Analysis')}.json", payload)

    def load_analysis(self, name: str, analysis: str) -> dict[str, Any]:
        raw = self._analyses(name).read(f"{validate_name(analysis, label='Analysis')}.json")
        return json.loads(raw.decode("utf-8"))

    def delete_analysis(self, name: str, analysis: str) -> None:
        self._analyses(name).delete(f"{validate_name(analysis, label='Analysis')}.json")
