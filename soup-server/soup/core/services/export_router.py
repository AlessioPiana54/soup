"""
------------------------------------------------------------------------
File : export_router.py
Description: ExportRouter - offers the exporters that accept an object's
             kind and runs one of them, after validating its options,
             into a file named after the object.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from soup.core.contracts import Exporter, Field, NotFoundError, ObjectRef
from soup.core.field_validation import validate_values
from soup.core.registry import Registry
from soup.core.services.core_tools import CoreTools, ObjectLike, kinds_of
from soup.core.toolbox import ToolBox


@dataclass(frozen=True)
class ExportedFile:
    filename: str
    mime: str
    content: bytes


class ExportRouter:
    def __init__(self, exporters: Registry[Exporter], core_tools: CoreTools):
        self._exporters = exporters
        self._core_tools = core_tools

    def exporters_for(self, obj: ObjectLike) -> list[Exporter]:
        ref = self._core_tools.object(obj)
        found = [exporter for exporter in self._exporters if self._applies(exporter, ref)]
        return sorted(found, key=lambda exporter: (exporter.label.lower(), exporter.id))

    def fields(self, exporter_id: str, obj: ObjectLike) -> list[Field]:
        exporter, ref = self._resolve(exporter_id, obj)
        return self._fields(exporter, ref, self._toolbox(exporter))

    def export(self, exporter_id: str, obj: ObjectLike, params: Optional[Mapping[str, Any]] = None) -> ExportedFile:
        exporter, ref = self._resolve(exporter_id, obj)
        tools = self._toolbox(exporter)
        cleaned = validate_values(self._fields(exporter, ref, tools), params)
        content = exporter.export(ref, cleaned, tools)
        if not isinstance(content, (bytes, bytearray)):
            raise TypeError(f"Exporter '{exporter.id}'.export() must return bytes, not {type(content).__name__}")
        return ExportedFile(filename=f"{ref.name}{exporter.extension}", mime=exporter.mime, content=bytes(content))

    # ------------------------------------------------------------------ #
    def _applies(self, exporter: Exporter, obj: ObjectRef) -> bool:
        return obj.kind in kinds_of(exporter.accepts) and self._core_tools.available(exporter.requires_tools)

    def _resolve(self, exporter_id: str, obj: ObjectLike) -> tuple[Exporter, ObjectRef]:
        ref = self._core_tools.object(obj)
        exporter = self._exporters.get(exporter_id)
        if exporter is None or not self._applies(exporter, ref):
            raise NotFoundError(f"Exporter '{exporter_id}' is not available for object '{ref.id}'")
        return exporter, ref

    def _toolbox(self, exporter: Exporter) -> ToolBox:
        return self._core_tools.toolbox(f"exporter '{exporter.id}'", exporter.requires_tools)

    @staticmethod
    def _fields(exporter: Exporter, obj: ObjectRef, tools: ToolBox) -> list[Field]:
        fields = list(exporter.fields(obj, tools) or [])
        for item in fields:
            if not isinstance(item, Field):
                raise TypeError(f"Exporter '{exporter.id}'.fields() must return Fields, got {type(item).__name__}")
        return fields
