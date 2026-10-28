"""
------------------------------------------------------------------------
File : text.py
Description: The two contributions of the template package:
             - TextImporter ("text"): reads a .txt file into an object of
               kind "template.text"; the lines are kept in the object's
               meta (no tool needed), at most `max_lines` of them.
             - TextVisualizer ("text"): shows "template.text" objects
               with the <soup-template-text> element of app/; data() gives
               the lines, action("stats") counts lines, words and
               characters.
             - StatsReport ("stats_report"): an operation from a
               "template.text" object to a "report" (drawn by soup_base,
               when active): counts and the longest lines as blocks.
             Copy and rename them to start a real importer/visualizer/
             operation.
Project : soup-packages/_template
------------------------------------------------------------------------
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from soup.core.contracts import (
    Field,
    Importer,
    Inspection,
    NotFoundError,
    ObjectDraft,
    ObjectRef,
    Operation,
    OperationInput,
    ToolAccess,
    Upload,
    Visualizer,
    report,
)

KIND = "template.text"
DEFAULT_MAX_LINES = 200
PREVIEW_LINES = 10


def _lines(upload: Upload) -> list[str]:
    return upload.read().decode("utf-8", errors="replace").splitlines()


def _stats(lines: list[str]) -> dict[str, int]:
    return {
        "lines": len(lines),
        "words": sum(len(line.split()) for line in lines),
        "characters": sum(len(line) for line in lines),
    }


def _max_lines(options: Mapping[str, Any]) -> int:
    return max(1, int(options.get("max_lines") or DEFAULT_MAX_LINES))


class TextImporter(Importer):
    id = "text"
    label = "Text file (template)"
    description = "Keeps the lines of a text file; an example to copy."
    extensions = (".txt",)
    produces = KIND

    def inspect(self, upload: Upload, tools: ToolAccess) -> Inspection:
        lines = _lines(upload)
        return Inspection(
            preview=(report.text("\n".join(lines[:PREVIEW_LINES]), title=f"First lines ({len(lines)} in total)"),),
            fields=(
                Field("max_lines", "Lines to keep", type="number", default=DEFAULT_MAX_LINES,
                      help="Only the first lines of the file are kept."),
            ),
        )

    def preview(self, upload: Upload, options: Mapping[str, Any], tools: ToolAccess) -> list[dict[str, Any]]:
        lines = _lines(upload)
        kept = min(len(lines), _max_lines(options))
        return [report.keyvalue({"lines in the file": len(lines), "lines kept": kept})]

    def import_(self, upload: Upload, obj: ObjectRef, options: Mapping[str, Any], tools: ToolAccess) -> dict[str, Any]:
        lines = _lines(upload)
        kept = lines[:_max_lines(options)]
        return {"filename": upload.filename, "total_lines": len(lines), "lines": kept}

    def dispose(self, obj: ObjectRef, tools: ToolAccess) -> None:
        # Everything lives in the object's meta: nothing to clean up.
        pass


class TextVisualizer(Visualizer):
    id = "text"
    label = "Text"
    accepts = (KIND,)
    element = "soup-template-text"

    def data(self, obj: ObjectRef, params: Mapping[str, Any], tools: ToolAccess) -> Any:
        return {
            "filename": obj.meta.get("filename", ""),
            "total_lines": obj.meta.get("total_lines", 0),
            "lines": list(obj.meta.get("lines") or []),
        }

    def action(self, obj: ObjectRef, name: str, params: Mapping[str, Any], tools: ToolAccess) -> Any:
        if name != "stats":
            raise NotFoundError(f"Visualizer '{self.id}' has no action '{name}'")
        return _stats([str(line) for line in obj.meta.get("lines") or []])


class StatsReport(Operation):
    id = "stats_report"
    label = "Text statistics (report)"
    description = "Counts lines, words and characters and lists the longest lines."
    group = "Template"
    inputs = (OperationInput("text", (KIND,)),)
    produces = (report.REPORT,)

    def fields(self, inputs: Mapping[str, ObjectRef], tools: ToolAccess) -> list[Field]:
        return [Field("top", "Longest lines", type="number", default=5)]

    def run(self, inputs: Mapping[str, ObjectRef], params: Mapping[str, Any], tools: ToolAccess) -> list[ObjectDraft]:
        source = inputs["text"]
        lines = [str(line) for line in source.meta.get("lines") or []]
        top = max(1, int(params.get("top") or 5))
        longest = sorted(enumerate(lines, start=1), key=lambda item: -len(item[1]))[:top]
        blocks = [
            report.keyvalue(_stats(lines), title="Counts"),
            report.table(["line", "length", "text"],
                [[n, len(text), text] for n, text in longest],
                title="Longest lines"),
            report.text("\n".join(lines), title="Text"),
        ]
        return [report.report(f"{source.name} statistics", blocks)]
