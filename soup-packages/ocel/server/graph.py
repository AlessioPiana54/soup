"""
------------------------------------------------------------------------
File : graph.py
Description: The OCEL 2.0 log as an EKG on Memgraph, through the ekg
             package (build_ekg, dispose):
             - event_log_data(log): the separated form of EventLogData
               with a fixed mapping - the id, the time (in UTC, without
               the offset, as localDateTime reads it) and the type of
               each event as event id, timestamp and activity; the object
               types as entity types (the ekg package adds one column per
               type and links the events to their objects); the event
               attributes as :Event properties (a name equal to a
               reserved one or to an object type takes a suffix). The
               qualifiers of the event-object relationships and the
               object-object relationships are not in the graph: the
               meta says so (ocel.not_in_graph, notice).
             - OcelEkgImporter ("ekg", "OCEL 2.0 come EKG su Memgraph").
             - DecomposeToEkg ("to_ekg", "Scomponi in EKG"): the same, from
               an "ocel_tables" object (read through the plugin's cache);
               the "ekg" object is its child.
Project : soup-packages/ocel
------------------------------------------------------------------------
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import timezone
from typing import Any

from soup_pkg_ekg.api import EKG_KIND, ColumnMapping, EventLogData, Table, build_ekg, dispose

from soup.core.contracts import ObjectDraft, ObjectRef, Operation, OperationInput, ToolAccess, Upload

from .model import OcelLog, Scalar, parse, parse_time
from .store import FORMAT_ID, MEMGRAPH, STORAGE, TABLES_KIND, OcelImporterBase, extension_of
from .tables_cache import CachedTables

EVENT_ID, ACTIVITY, TIMESTAMP = "ocel:eid", "ocel:activity", "ocel:timestamp"
# The columns of the canonical events CSV and the properties of the :Event
# nodes written by the ekg package: an attribute cannot take these names.
_RESERVED = {EVENT_ID, ACTIVITY, TIMESTAMP,
    "event_id", "timestamp", "activity_name", "Event_Id", "Timestamp", "ActivityName"}
_WHITESPACE = re.compile(r"\s+")

NOT_IN_GRAPH = ("qualifiers", "object_objects")


def _normalized(name: str) -> str:
    """How the ekg package names a column (spaces collapsed into "_")."""

    return _WHITESPACE.sub("_", name.strip())


def graph_time(value: str) -> str:
    """An ISO 8601 time as localDateTime reads it: UTC, no offset, milliseconds."""

    when = parse_time(value)
    if when.tzinfo is not None:
        when = when.astimezone(timezone.utc).replace(tzinfo=None)
    return when.isoformat(timespec="milliseconds")


def _text(value: Scalar) -> Any:
    if value is None or isinstance(value, str):
        return value
    return json.dumps(value)


def attribute_columns(log: OcelLog) -> dict[str, str]:
    """Attribute name -> its column in the events table, never a reserved name nor an object type."""

    names = dict.fromkeys(
        [name for decl in log.event_types for name, _type in decl.attributes]
        + [name for event in log.events for name, _value in event.attributes]
    )
    taken = {_normalized(name) for name in _RESERVED} | {_normalized(decl.name) for decl in log.object_types}
    columns: dict[str, str] = {}
    for name in names:
        column, suffix = name, 1
        while _normalized(column) in taken:
            column = f"{name}_attribute" if suffix == 1 else f"{name}_attribute_{suffix}"
            suffix += 1
        taken.add(_normalized(column))
        columns[name] = column
    return columns


def event_log_data(log: OcelLog) -> tuple[EventLogData, ColumnMapping]:
    columns = attribute_columns(log)
    rows = []
    for event in log.events:
        values = dict(event.attributes)
        rows.append((event.id, event.type, graph_time(event.time), *(_text(values.get(name)) for name in columns)))
    events = Table((EVENT_ID, ACTIVITY, TIMESTAMP, *columns.values()), tuple(rows))
    objects = Table(("object_id", "object_type"), tuple((obj.id, obj.type) for obj in log.objects))
    event_objects = Table(
        ("event_id", "object_id", "qualifier"),
        tuple((event.id, link.object_id, link.qualifier) for event in log.events for link in event.relationships),
    )
    mapping = ColumnMapping(
        event_id=EVENT_ID, timestamp=TIMESTAMP, activity=ACTIVITY, value_columns=tuple(columns.values()),
    )
    return EventLogData(events=events, objects=objects, event_objects=event_objects), mapping


def ocel_meta(log: OcelLog, extension: str) -> dict[str, Any]:
    """What an "ekg" made from an OCEL log adds to the meta of build_ekg."""

    counts = log.counts()
    qualified = sum(1 for event in log.events for link in event.relationships if link.qualifier)
    return {
        "ocel": {
            "extension": extension,
            "counts": counts,
            "qualified_event_objects": qualified,
            "not_in_graph": list(NOT_IN_GRAPH),
        },
        "notice": (
            "Dal log OCEL 2.0 non entrano nel grafo i qualifier delle relazioni evento-oggetto "
            f"({qualified} con qualifier) e le relazioni oggetto-oggetto ({counts['object_objects']})."
        ),
    }


def build(obj: Any, log: OcelLog, extension: str, tools: ToolAccess) -> dict[str, Any]:
    data, mapping = event_log_data(log)
    meta = build_ekg(obj, data, mapping, tools, source_format=FORMAT_ID)
    return {**meta, **ocel_meta(log, extension)}


class OcelEkgImporter(OcelImporterBase):
    id = "ekg"
    label = "OCEL 2.0 come EKG su Memgraph"
    description = (
        "Scompone il log in un EKG su Memgraph: id, time e type di ogni evento, i tipi di oggetto come tipi "
        "di entità e gli attributi degli eventi come proprietà. I qualifier delle relazioni evento-oggetto e "
        "le relazioni oggetto-oggetto non entrano nel grafo."
    )
    produces = EKG_KIND
    requires_tools = (MEMGRAPH, STORAGE)

    def import_(self, upload: Upload, obj: ObjectRef, options: Mapping[str, Any], tools: ToolAccess) -> dict[str, Any]:
        log = parse(upload.read())
        return {**build(obj, log, extension_of(upload.filename), tools), "filename": upload.filename}

    def dispose(self, obj: ObjectRef, tools: ToolAccess) -> None:
        dispose(obj, tools)


class DecomposeToEkg(CachedTables, Operation):
    id = "to_ekg"
    label = "Scomponi in EKG"
    description = (
        "Costruisce su Memgraph l'EKG delle tabelle OCEL, come l'importer \"OCEL 2.0 come EKG\": "
        "qualifier e relazioni oggetto-oggetto non entrano nel grafo."
    )
    group = "EKG"
    inputs = (OperationInput("tables", (TABLES_KIND,)),)
    produces = (EKG_KIND,)
    requires_tools = (MEMGRAPH, STORAGE)

    def run(self, inputs: Mapping[str, ObjectRef], params: Mapping[str, Any], tools: ToolAccess) -> list[ObjectDraft]:
        source = inputs["tables"]
        log = self._tables(source, tools).log()
        extension = extension_of(str(source.meta.get("filename") or ""))
        draft = ObjectDraft(name=f"{source.name[:120].rstrip()} (EKG)", kind=EKG_KIND, description=source.description)
        draft.meta = build(draft, log, extension, tools)
        return [draft]

    def dispose(self, obj: ObjectRef, tools: ToolAccess) -> None:
        dispose(obj, tools)
