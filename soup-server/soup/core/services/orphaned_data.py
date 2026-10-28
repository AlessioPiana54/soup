"""
------------------------------------------------------------------------
File : orphaned_data.py
Description: OrphanedDataLog - objects removed from the catalog with
             force=true while the package that created them was not
             active, so their data (graph nodes, files, ...) could not be
             disposed of. Each entry keeps the object (with its meta,
             which says where the data lives), the package and the
             contributor, so the leftovers can be cleaned up later. Stored
             as a JSON list in <installed packages folder>/orphaned-data.json,
             written atomically (temporary file + os.replace).
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import json
import logging
import os
import threading
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from soup.core.contracts import ObjectRef
from soup.core.services.core_tools import timestamp

ORPHANED_DATA_FILE = "orphaned-data.json"

_LOGGER = logging.getLogger("soup.workspace")


class OrphanedDataLog:
    def __init__(self, path: str | Path, clock: Callable[[], datetime] = datetime.now):
        self.path = Path(path)
        self._clock = clock
        self._lock = threading.Lock()

    def record(self, obj: ObjectRef) -> None:
        entry = {
            "object": obj.to_dict(),
            "package": obj.created_by.package,
            "contributor": obj.created_by.to_dict(),
            "removed_at": timestamp(self._clock),
        }
        with self._lock:
            entries = self._read()
            entries.append(entry)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_name(self.path.name + ".tmp")
            temporary.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
            os.replace(temporary, self.path)

    def entries(self) -> list[dict[str, Any]]:
        with self._lock:
            return self._read()

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            # Never lose new entries because of an unreadable file: keep it aside.
            backup = self.path.with_name(self.path.name + ".corrupt")
            _LOGGER.warning("Unreadable '%s' (%s): moved to '%s'", self.path, exc, backup)
            os.replace(self.path, backup)
            return []
        return data if isinstance(data, list) else []
