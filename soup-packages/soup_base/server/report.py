"""
------------------------------------------------------------------------
File : report.py
Description: The contributions of soup_base for the "report" kind (the
             only kind the core defines, soup/core/contracts/report.py):
             - ReportVisualizer ("report"): <soup-report-view> draws
               meta.blocks one under the other; data() gives the blocks
               with the name and description of the object.
             - ReportJsonExporter ("json"): the report as an indented
               JSON file {name, description, created_at, blocks}.
Project : soup-packages/soup_base
------------------------------------------------------------------------
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from soup.core.contracts import REPORT, Exporter, ObjectRef, ToolAccess, Visualizer


def _blocks(obj: ObjectRef) -> list[Any]:
    blocks = obj.meta.get("blocks")
    return list(blocks) if isinstance(blocks, list) else []


class ReportVisualizer(Visualizer):
    id = "report"
    label = "Report"
    accepts = (REPORT,)
    element = "soup-report-view"

    def data(self, obj: ObjectRef, params: Mapping[str, Any], tools: ToolAccess) -> Any:
        return {"name": obj.name, "description": obj.description, "blocks": _blocks(obj)}


class ReportJsonExporter(Exporter):
    id = "json"
    label = "Report in JSON"
    accepts = (REPORT,)
    extension = ".json"
    mime = "application/json"

    def export(self, obj: ObjectRef, params: Mapping[str, Any], tools: ToolAccess) -> bytes:
        document = {
            "name": obj.name,
            "description": obj.description,
            "created_at": obj.created_at,
            "blocks": _blocks(obj),
        }
        return json.dumps(document, ensure_ascii=False, indent=2).encode("utf-8")
