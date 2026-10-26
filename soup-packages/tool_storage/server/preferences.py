"""
------------------------------------------------------------------------
File : preferences.py
Description: FilePreferences - the "preferences" tool: a flat key ->
             JSON value store in <root>/_catalog/preferences.json. It
             takes the place of the onboarding node the legacy code keeps
             in Memgraph, so preferences survive switching the active
             graph.
Project : soup-packages/tool_storage
------------------------------------------------------------------------
"""

from __future__ import annotations

import json
import threading
from typing import Any

from soup.core.contracts import FileStorage, Preferences, ValidationError

from .catalog import CATALOG_DIR
from .storage import guard_os_errors

PREFERENCES_PATH = f"{CATALOG_DIR}/preferences.json"


class FilePreferences(Preferences):
    def __init__(self, backend: FileStorage):
        self._backend = backend
        self._lock = threading.Lock()

    def health(self) -> dict[str, Any]:
        try:
            self._load()
        except Exception as exc:  # noqa: BLE001 - health() must not raise
            return {"ok": False, "error": str(exc)}
        return {"ok": True}

    def get(self, key: str) -> Any:
        return self._load().get(_check_key(key))

    def set(self, key: str, value: Any) -> None:
        _check_key(key)
        with self._lock:
            values = self._load()
            values[key] = value
            try:
                payload = json.dumps(values, indent=2, ensure_ascii=False).encode("utf-8")
            except (TypeError, ValueError) as exc:
                raise ValidationError(f"Preference '{key}' is not JSON-serializable: {exc}") from exc
            guard_os_errors("Preferences", self._backend.write, PREFERENCES_PATH, payload)

    def _load(self) -> dict[str, Any]:
        if not guard_os_errors("Preferences", self._backend.exists, PREFERENCES_PATH):
            return {}
        raw = guard_os_errors("Preferences", self._backend.read, PREFERENCES_PATH)
        values = json.loads(raw.decode("utf-8"))
        return values if isinstance(values, dict) else {}


def _check_key(key: Any) -> str:
    if not isinstance(key, str) or not key:
        raise ValidationError(f"A preference key must be a non-empty string, got {key!r}")
    return key
