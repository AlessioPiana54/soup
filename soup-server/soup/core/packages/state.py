"""
------------------------------------------------------------------------
File : state.py
Description: PackageState - which packages the user disabled, persisted
             in <installed packages folder>/_state.json as
             {"disabled": [...]}. A package name cannot start with "_",
             so the file never collides with a package folder. A missing
             or unreadable file means every package is enabled. Writes
             are atomic (temporary file + os.replace).
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

STATE_FILE = "_state.json"

_LOGGER = logging.getLogger("soup.packages")


class PackageState:
    def __init__(self, directory: str | Path):
        self.path = Path(directory) / STATE_FILE
        self._disabled: set[str] = self._read()

    @property
    def disabled(self) -> frozenset[str]:
        return frozenset(self._disabled)

    def is_disabled(self, name: str) -> bool:
        return name in self._disabled

    def set_disabled(self, name: str, disabled: bool) -> None:
        if disabled == (name in self._disabled):
            return
        if disabled:
            self._disabled.add(name)
        else:
            self._disabled.discard(name)
        self._write()

    def forget(self, name: str) -> None:
        self.set_disabled(name, False)

    def _read(self) -> set[str]:
        if not self.path.is_file():
            return set()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return {name for name in data.get("disabled", []) if isinstance(name, str)}
        except (OSError, ValueError, AttributeError) as exc:
            _LOGGER.warning("Ignoring unreadable package state '%s': %s", self.path, exc)
            return set()

    def _write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + ".tmp")
        temporary.write_text(json.dumps({"disabled": sorted(self._disabled)}, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, self.path)
