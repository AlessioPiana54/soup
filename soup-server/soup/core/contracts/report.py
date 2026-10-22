"""
------------------------------------------------------------------------
File : report.py
Description: The "report" kind - the only kind the core defines, for
             simple results (statistics, short analyses, previews). The
             core only fixes the format; displaying it is a package's job.
             A report object carries meta["blocks"]: a list of blocks
             {type, title, data}, where `type` is one of BLOCK_TYPES and
             `data` has the shape of its type:

             - text      {text}
             - markdown  {markdown}
             - image     {mime, base64} or {svg}
             - table     {columns: [str], rows: [[cell]], total?: int}
                         (`total` is the full row count when `rows` is
                         truncated)
             - graph     {nodes: [{id, label, group, props}],
                          edges: [{id, source, target, label, group, props}],
                          directed: bool}
             - chart     {chart: "pie"|"bar"|"line", labels: [str],
                          datasets: [{label, data: [number]}]}
             - keyvalue  {items: [{key, value}]}
             - file      {filename, mime, base64}
             - error     {message}

             The same block format is used by Importer.inspect/preview.
             The factory functions below build valid blocks as plain
             JSON-ready dicts.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import base64 as _base64
from typing import Any, Iterable, Mapping, Optional, Sequence, Union

from soup.core.contracts.objects import ObjectDraft

REPORT = "report"

TEXT = "text"
MARKDOWN = "markdown"
IMAGE = "image"
TABLE = "table"
GRAPH = "graph"
CHART = "chart"
KEYVALUE = "keyvalue"
FILE = "file"
ERROR = "error"

BLOCK_TYPES = (TEXT, MARKDOWN, IMAGE, TABLE, GRAPH, CHART, KEYVALUE, FILE, ERROR)

CHART_KINDS = ("pie", "bar", "line")

# Keys `data` must contain, per block type (image is checked separately:
# it needs either {mime, base64} or {svg}).
_REQUIRED_KEYS: dict[str, tuple[str, ...]] = {
    TEXT: ("text",),
    MARKDOWN: ("markdown",),
    IMAGE: (),
    TABLE: ("columns", "rows"),
    GRAPH: ("nodes", "edges"),
    CHART: ("chart", "labels", "datasets"),
    KEYVALUE: ("items",),
    FILE: ("filename", "mime", "base64"),
    ERROR: ("message",),
}


def validate_block(block: Any) -> dict[str, Any]:
    """
    Check one block and return it as a fresh {type, title, data} dict.
    :raises ValueError: unknown type, or `data` not of the type's shape
    """

    if not isinstance(block, Mapping):
        raise ValueError(f"A block must be an object {{type, title, data}}, got {type(block).__name__}")
    block_type = block.get("type")
    if block_type not in BLOCK_TYPES:
        raise ValueError(f"Unknown block type {block_type!r}; expected one of {BLOCK_TYPES}")
    data = block.get("data")
    if not isinstance(data, Mapping):
        raise ValueError(f"Block of type {block_type!r}: data must be an object")
    missing = [key for key in _REQUIRED_KEYS[block_type] if key not in data]
    if missing:
        raise ValueError(f"Block of type {block_type!r} is missing data keys {missing}")
    if block_type == IMAGE and "svg" not in data and not ("mime" in data and "base64" in data):
        raise ValueError("Block of type 'image' needs either {mime, base64} or {svg}")
    if block_type == CHART and data["chart"] not in CHART_KINDS:
        raise ValueError(f"Chart kind must be one of {CHART_KINDS}, got {data['chart']!r}")
    title = block.get("title") or ""
    if not isinstance(title, str):
        raise ValueError("Block title must be a string")
    return {"type": block_type, "title": title, "data": dict(data)}


def validate_blocks(blocks: Any) -> list[dict[str, Any]]:
    if not isinstance(blocks, (list, tuple)):
        raise ValueError("Blocks must be a list")
    return [validate_block(block) for block in blocks]


def report(name: str, blocks: Iterable[Mapping[str, Any]], description: str = "") -> ObjectDraft:
    """An ObjectDraft of kind "report" carrying `blocks`."""

    return ObjectDraft(name=name, kind=REPORT, meta={"blocks": validate_blocks(list(blocks))}, description=description)


# ---------------------------------------------------------------------- #
# Block factories
# ---------------------------------------------------------------------- #
def make_block(block_type: str, data: Mapping[str, Any], title: str = "") -> dict[str, Any]:
    return validate_block({"type": block_type, "title": title, "data": data})


def text(value: str, title: str = "") -> dict[str, Any]:
    return make_block(TEXT, {"text": value}, title)


def markdown(value: str, title: str = "") -> dict[str, Any]:
    return make_block(MARKDOWN, {"markdown": value}, title)


def image(content: bytes, mime: str, title: str = "") -> dict[str, Any]:
    return make_block(IMAGE, {"mime": mime, "base64": _base64.b64encode(content).decode("ascii")}, title)


def svg(markup: str, title: str = "") -> dict[str, Any]:
    return make_block(IMAGE, {"svg": markup}, title)


def table(
    columns: Sequence[str], rows: Iterable[Sequence[Any]], total: Optional[int] = None, title: str = ""
) -> dict[str, Any]:
    data: dict[str, Any] = {"columns": list(columns), "rows": [list(row) for row in rows]}
    if total is not None:
        data["total"] = total
    return make_block(TABLE, data, title)


def graph(
    nodes: Iterable[Mapping[str, Any]], edges: Iterable[Mapping[str, Any]], directed: bool = True, title: str = ""
) -> dict[str, Any]:
    node_list = [
        {
            "id": str(node["id"]),
            "label": node.get("label", str(node["id"])),
            "group": node.get("group", ""),
            "props": dict(node.get("props") or {}),
        }
        for node in nodes
    ]
    edge_list = [
        {
            "id": str(edge.get("id", f"{edge['source']}->{edge['target']}#{index}")),
            "source": str(edge["source"]),
            "target": str(edge["target"]),
            "label": edge.get("label", ""),
            "group": edge.get("group", ""),
            "props": dict(edge.get("props") or {}),
        }
        for index, edge in enumerate(edges)
    ]
    return make_block(GRAPH, {"nodes": node_list, "edges": edge_list, "directed": directed}, title)


def chart(chart_kind: str, labels: Sequence[str], datasets: Iterable[Mapping[str, Any]], title: str = "") -> dict[str, Any]:
    dataset_list = [{"label": item.get("label", ""), "data": list(item["data"])} for item in datasets]
    return make_block(CHART, {"chart": chart_kind, "labels": list(labels), "datasets": dataset_list}, title)


def keyvalue(items: Union[Mapping[str, Any], Iterable[tuple[str, Any]]], title: str = "") -> dict[str, Any]:
    pairs = items.items() if isinstance(items, Mapping) else items
    return make_block(KEYVALUE, {"items": [{"key": key, "value": value} for key, value in pairs]}, title)


def file(filename: str, content: bytes, mime: str = "application/octet-stream", title: str = "") -> dict[str, Any]:
    encoded = _base64.b64encode(content).decode("ascii")
    return make_block(FILE, {"filename": filename, "mime": mime, "base64": encoded}, title)


def error(message: str, title: str = "") -> dict[str, Any]:
    return make_block(ERROR, {"message": message}, title)
