"""
------------------------------------------------------------------------
File : local_storage.py
Description: FileStorage adapter backed by the local filesystem.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import shutil
from pathlib import Path

from soup.core.contracts import FileStorage


class LocalFileStorage(FileStorage):
    def __init__(self, root: str):
        self._root = Path(root)

    def _resolve(self, path: str) -> Path:
        return self._root / path.lstrip("/\\")

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

    def list(self, prefix: str = "") -> list[str]:
        base = self._resolve(prefix) if prefix else self._root
        if not base.exists():
            return []
        return sorted(p.name for p in base.iterdir())
