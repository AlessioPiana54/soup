"""
------------------------------------------------------------------------
File : storage.py
Description: StorageTool - the "storage" tool. Files are grouped in
             namespaces: storage.space(namespace) is a FileStorage whose
             read/write/exists/delete/list are relative to
             <root>/<namespace>/, and storage.path_for(namespace, name) is
             the absolute path of a file for whoever hands it to
             Memgraph (LOAD CSV reads from the same /soup volume). Each
             package uses its own namespace; an EKG dataset keeps its
             /soup/<name>/ folder (namespace = dataset name).
             Namespaces and file names go through validate_name, so ""
             "..", separators and a leading "_" are refused: "_catalog",
             where the catalog and the preferences live, is out of reach.
Project : soup-packages/tool_storage
------------------------------------------------------------------------
"""

from __future__ import annotations

import posixpath
from typing import Any

from soup.core.contracts import (
    FileStorage,
    NotFoundError,
    ServiceUnavailableError,
    Tool,
    validate_name,
)

STORAGE_TOOL = "storage"


def _namespace(namespace: str) -> str:
    return validate_name(namespace, label="Namespace")


def _file_name(name: str) -> str:
    return validate_name(name, label="File")


def guard_os_errors(what: str, call, *args):
    """Run a backend call: missing file -> NotFoundError, other OS errors -> 503."""

    try:
        return call(*args)
    except FileNotFoundError:
        raise NotFoundError(f"{what} not found") from None
    except IsADirectoryError:
        raise NotFoundError(f"{what} not found") from None
    except OSError as exc:
        raise ServiceUnavailableError(f"File storage is not available: {exc}") from exc


class StorageSpace(FileStorage):
    """The files of one namespace. `list()` returns their names."""

    def __init__(self, backend: FileStorage, namespace: str):
        self._backend = backend
        self.namespace = _namespace(namespace)

    def _path(self, name: str) -> str:
        return f"{self.namespace}/{_file_name(name)}"

    def read(self, path: str) -> bytes:
        return guard_os_errors(f"File '{self.namespace}/{path}'", self._backend.read, self._path(path))

    def write(self, path: str, data: bytes) -> None:
        guard_os_errors(f"File '{self.namespace}/{path}'", self._backend.write, self._path(path), bytes(data))

    def exists(self, path: str) -> bool:
        return guard_os_errors(f"File '{self.namespace}/{path}'", self._backend.exists, self._path(path))

    def delete(self, path: str) -> None:
        guard_os_errors(f"File '{self.namespace}/{path}'", self._backend.delete, self._path(path))

    def list(self, prefix: str = "") -> list[str]:
        names = guard_os_errors(f"Namespace '{self.namespace}'", self._backend.list, self.namespace)
        return sorted(name for name in names if name.startswith(prefix))


class StorageTool(Tool):
    name = STORAGE_TOOL

    def __init__(self, backend: FileStorage, root: str = "/soup"):
        self._backend = backend
        self._root = root.rstrip("/") or "/"

    def space(self, namespace: str) -> StorageSpace:
        return StorageSpace(self._backend, namespace)

    def path_for(self, namespace: str, name: str) -> str:
        """Absolute path of <namespace>/<name> under the root, e.g. for LOAD CSV."""

        return posixpath.join(self._root, _namespace(namespace), _file_name(name))

    def delete_space(self, namespace: str) -> None:
        """Remove the namespace and every file in it (no-op if it does not exist)."""

        guard_os_errors(f"Namespace '{namespace}'", self._backend.delete, _namespace(namespace))

    def health(self) -> dict[str, Any]:
        try:
            self._backend.list("")
        except Exception as exc:  # noqa: BLE001 - health() must not raise
            return {"ok": False, "error": str(exc)}
        return {"ok": True}
