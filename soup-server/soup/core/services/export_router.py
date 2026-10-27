"""
------------------------------------------------------------------------
File : export_router.py
Description: ExportRouter - offers the exporters that accept an object's
             kind (and apply to it: Exporter.applies) and runs one of
             them, after validating its options, into a file named after
             the object. Exporters are addressed by their full key
             "<package>.<id>" (exporters_for() lists them with their key
             and package). An exporter that does not apply to an object,
             or whose applies() raises (logged with its package), is not
             listed and its export answers NotFoundError, like an unknown
             one.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Mapping, Optional

from soup.core.contracts import Exporter, Field, NotFoundError, ObjectRef
from soup.core.field_validation import validate_values
from soup.core.registry import Registered, Registry
from soup.core.services.core_tools import CoreTools, ObjectLike, kinds_of
from soup.core.toolbox import ToolBox

_LOGGER = logging.getLogger("soup.export")


@dataclass(frozen=True)
class ExportedFile:
    filename: str
    mime: str
    content: bytes


class ExportRouter:
    def __init__(self, exporters: Registry[Exporter], core_tools: CoreTools):
        self._exporters = exporters
        self._core_tools = core_tools

    def exporters_for(self, obj: ObjectLike) -> list[Registered[Exporter]]:
        ref = self._core_tools.object(obj)
        found = [entry for entry in self._exporters.entries() if self._applies(entry, ref)]
        return sorted(found, key=lambda entry: (entry.item.label.lower(), entry.key))

    def fields(self, exporter_id: str, obj: ObjectLike) -> list[Field]:
        exporter, ref = self._resolve(exporter_id, obj)
        return self._fields(exporter, ref, self._toolbox(exporter_id, exporter))

    def export(self, exporter_id: str, obj: ObjectLike, params: Optional[Mapping[str, Any]] = None) -> ExportedFile:
        exporter, ref = self._resolve(exporter_id, obj)
        tools = self._toolbox(exporter_id, exporter)
        cleaned = validate_values(self._fields(exporter, ref, tools), params)
        content = exporter.export(ref, cleaned, tools)
        if not isinstance(content, (bytes, bytearray)):
            raise TypeError(f"Exporter '{exporter.id}'.export() must return bytes, not {type(content).__name__}")
        return ExportedFile(filename=f"{ref.name}{exporter.extension}", mime=exporter.mime, content=bytes(content))

    # ------------------------------------------------------------------ #
    def _applies(self, entry: Registered[Exporter], obj: ObjectRef) -> bool:
        exporter = entry.item
        if obj.kind not in kinds_of(exporter.accepts) or not self._core_tools.available(exporter.requires_tools):
            return False
        try:
            return bool(exporter.applies(obj, self._toolbox(entry.key, exporter)))
        except Exception:  # noqa: BLE001 - one broken exporter must not break the list
            _LOGGER.exception("Exporter '%s' of package '%s' failed in applies()", entry.key, entry.package)
            return False

    def _resolve(self, exporter_id: str, obj: ObjectLike) -> tuple[Exporter, ObjectRef]:
        ref = self._core_tools.object(obj)
        entry = next((item for item in self._exporters.entries() if item.key == exporter_id), None)
        if entry is None or not self._applies(entry, ref):
            raise NotFoundError(f"Exporter '{exporter_id}' is not available for object '{ref.id}'")
        return entry.item, ref

    def _toolbox(self, key: str, exporter: Exporter) -> ToolBox:
        return self._core_tools.toolbox(f"exporter '{key}'", exporter.requires_tools)

    @staticmethod
    def _fields(exporter: Exporter, obj: ObjectRef, tools: ToolBox) -> list[Field]:
        fields = list(exporter.fields(obj, tools) or [])
        for item in fields:
            if not isinstance(item, Field):
                raise TypeError(f"Exporter '{exporter.id}'.fields() must return Fields, got {type(item).__name__}")
        return fields
