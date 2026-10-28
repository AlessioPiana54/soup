"""
------------------------------------------------------------------------
File : local.py
Description: FileStorage backend on the local filesystem (moved here from
             soup/infrastructure/local_storage.py). Paths are relative to
             the root; a path that resolves outside it is refused.
             list(prefix) returns the names of the entries directly under
             prefix, like the Docker backend.
Project : soup-packages/tool_storage
------------------------------------------------------------------------
"""

from __future__ import annotations

import builtins
import shutil
from pathlib import Path

from soup.core.contracts import FileStorage


class LocalFileStorage(FileStorage):
    def __init__(self, root: str):
        self._root = Path(root)

    def _resolve(self, path: str) -> Path:
        root = self._root.resolve()
        target = (root / path.lstrip("/\\")).resolve()
        if target != root and root not in target.parents:
            raise ValueError(f"Path {path!r} is outside the storage root")
        return target

    def read(self, path: str) -> bytes:
        return self._resolve(path).read_bytes()

    def write(self, path: str, data: bytes) -> None:
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def exists(self, path: str) -> bool:
        return self._resolve(path).exists()

    def delete(self, path: str) -> None:
        target = self._resolve(path)
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
        elif target.exists():
            target.unlink()

    def list(self, prefix: str = "") -> builtins.list[str]:
        base = self._resolve(prefix)
        if not base.is_dir():
            return []
        return sorted(p.name for p in base.iterdir())
