"""
------------------------------------------------------------------------
File : event_log.py
Description: ColumnMapping and EventLog - the core domain logic for the
             Import pillar. Everything that is common to every input
             format lives here (normalization, mapping validation, entity
             extraction, canonical CSV staging); a reader plugin only
             reads a file into an EventLogData (see
             soup/core/contracts/event_log.py).

             Behaviour intentionally reproduced from the legacy code
             (frontend NewDatasetComponent.parseFileData/prepareBuild and
             backend Services/Graph/graph_service.process_new_dataset_files),
             corrected where the legacy version was clearly a bug rather
             than the intent:
             - column/value whitespace normalization: the legacy
               NewDatasetComponent.processChunk() does
               `value.replace(/\\s+/g, '_').trim()` - replace-then-trim,
               which (since no whitespace survives the replace) leaves
               stray leading/trailing underscores on values with leading/
               trailing spaces. We strip first, then collapse internal
               whitespace, which is the evidently-intended behaviour and
               does not corrupt the superfluous-space fixture case.
             - millisecond comma -> dot: same regex idea as
               NewDatasetComponent.convertTimestampFormat(), applied only
               to the mapped timestamp column's values.
             - entity extraction splits multi-valued cells on ',',
               consistent with the :CORR query's split(e.key, ',') in
               Utils/graph_query_lib.py - the legacy entity-extraction
               code in process_new_dataset_files did NOT do this split,
               which is one of the documented bugs this refactor fixes.

             The canonical CSV staging format (events_csv/entities_csv)
             keeps the exact columns the current LOAD CSV queries expect
             (Utils/graph_query_lib.py, not modified by this session):
             load_event_node_query() reads row.<event_id col>,
             row.<timestamp col>, row.<activity col> plus one row.<key>
             per extra property; load_entity_node_query() reads
             row.value/row.type.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, replace
from typing import Optional, Sequence

from soup.core.contracts import EventLogData, Table
from soup.core.errors import ValidationError

# Canonical column names of the staged events CSV - these are exactly what
# Services/generic_graph_service.py passes as event_id_col/timestamp_col/
# activity_col to load_event_node_query() today (the frontend already
# renames the user's chosen columns to these 3 names before upload).
EVENT_ID_COLUMN = "event_id"
TIMESTAMP_COLUMN = "timestamp"
ACTIVITY_COLUMN = "activity_name"

_RESERVED_CANONICAL_NAMES = (EVENT_ID_COLUMN, TIMESTAMP_COLUMN, ACTIVITY_COLUMN)

_WHITESPACE_RE = re.compile(r"\s+")
_MILLIS_COMMA_RE = re.compile(r"(\d{2}:\d{2}:\d{2}),(\d{3})")

_OBJECT_ID = "object_id"
_OBJECT_TYPE = "object_type"
_EVENT_ID = "event_id"


def _normalize_text(value: str) -> str:
    """Strip leading/trailing whitespace, then collapse internal runs of whitespace to '_'."""

    return _WHITESPACE_RE.sub("_", value.strip())


def _fix_millis_comma(value: str) -> str:
    """'...HH:MM:SS,mmm' -> '...HH:MM:SS.mmm' (European decimal comma in milliseconds)."""

    return _MILLIS_COMMA_RE.sub(r"\1.\2", value)


def _split_multi_value(raw: str) -> list[str]:
    """Split a (possibly) comma-separated cell into trimmed, non-empty parts."""

    return [part.strip() for part in raw.split(",") if part.strip() != ""]


def _write_csv(columns: Sequence[str], rows: Sequence[Sequence[Optional[str]]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow("" if value is None else value for value in row)
    return buffer.getvalue().encode("utf-8")


@dataclass(frozen=True)
class ColumnMapping:
    """
    Which role each column of the events table plays. Mirrors the current
    /api/v2/graph import payload (Controllers/Graph/graph_controller.py):
    `standardColumn` (exactly 3: event id, timestamp, activity),
    `filteredColumn` (entity/object columns -> become :CORR-ed Entity
    nodes) and `valuesColumn` (columns kept as plain Event properties). A
    column may legitimately appear in both entity_columns and
    value_columns (the frontend lets a user tick both checkboxes for the
    same column). A column that is one of the 3 standard roles is dropped
    from entity_columns/value_columns on normalization (see _normalized) -
    it is already consumed by that role, so keeping it as an extra
    property/entity type would duplicate it (the canonical events CSV has
    no separate column for it - events_csv() already excludes it from
    extra_columns - and the legacy rebuild endpoint would otherwise emit a
    Cypher map literal with the same key twice, e.g. when the timestamp
    column is also ticked as a value column).
    """

    event_id: str
    timestamp: str
    activity: str
    entity_columns: tuple[str, ...] = ()
    value_columns: tuple[str, ...] = ()

    @classmethod
    def from_payload(
        cls,
        standard_columns: Sequence[str],
        filtered_columns: Sequence[str] = (),
        values_columns: Sequence[str] = (),
    ) -> "ColumnMapping":
        if len(standard_columns) != 3:
            raise ValidationError(
                "'standardColumn' must have exactly 3 entries: [event_id, timestamp, activity]"
            )
        event_id, timestamp, activity = standard_columns
        return cls(
            event_id=event_id,
            timestamp=timestamp,
            activity=activity,
            entity_columns=tuple(filtered_columns),
            value_columns=tuple(values_columns),
        )

    def _normalized(self) -> "ColumnMapping":
        event_id = _normalize_text(self.event_id)
        timestamp = _normalize_text(self.timestamp)
        activity = _normalize_text(self.activity)
        standard_roles = {event_id, timestamp, activity}
        return ColumnMapping(
            event_id=event_id,
            timestamp=timestamp,
            activity=activity,
            entity_columns=tuple(
                c for c in (_normalize_text(c) for c in self.entity_columns) if c not in standard_roles
            ),
            value_columns=tuple(
                c for c in (_normalize_text(c) for c in self.value_columns) if c not in standard_roles
            ),
        )

    def validate_against(self, columns: Sequence[str]) -> None:
        available = set(columns)
        referenced = {self.event_id, self.timestamp, self.activity, *self.entity_columns, *self.value_columns}
        missing = sorted(name for name in referenced if name not in available)
        if missing:
            raise ValidationError(f"Column mapping refers to columns missing from the data: {missing}")


@dataclass(frozen=True)
class EventLog:
    """
    Normalized, validated event log, ready to be staged as canonical CSV
    for LOAD CSV (events_csv/entities_csv).
    """

    mapping: ColumnMapping
    events: Table
    objects: Optional[Table] = None  # raw `objects` table (separated form only); feeds entity_table()

    # ------------------------------------------------------------------ #
    # Construction
    # ------------------------------------------------------------------ #
    @classmethod
    def from_data(cls, data: EventLogData, mapping: ColumnMapping) -> "EventLog":
        """
        Build an EventLog from whatever shape `data` is in (flat, or
        separated events/objects/event_objects), applying the same
        normalization/validation regardless of the source format.
        """

        objects_table: Optional[Table] = None

        if data.objects is not None and data.event_objects is not None:
            events_table, mapping = cls._merge_separated_into_flat(data, mapping)
            objects_table = data.objects
        else:
            events_table = data.events

        normalized_table, normalized_mapping = cls._normalize(events_table, mapping)
        return cls(mapping=normalized_mapping, events=normalized_table, objects=objects_table)

    @staticmethod
    def _merge_separated_into_flat(data: EventLogData, mapping: ColumnMapping) -> tuple[Table, ColumnMapping]:
        """
        Fold the separated form into the flat shape: one extra column per
        distinct object_type, each cell the comma-joined object_ids an
        event is linked to via `event_objects` (order of first appearance
        in event_objects, for that event). The resulting table is then
        handled by the exact same pipeline as a flat CSV.
        """

        objects = data.objects
        event_objects = data.event_objects
        assert objects is not None and event_objects is not None  # guarded by the caller

        object_type_by_id: dict[str, str] = {}
        obj_id_idx = objects.column_index(_OBJECT_ID)
        obj_type_idx = objects.column_index(_OBJECT_TYPE)
        for row in objects.rows:
            object_type_by_id[row[obj_id_idx]] = row[obj_type_idx]

        object_types = sorted(set(object_type_by_id.values()))

        # NOTE: event_objects may carry an optional `qualifier` column
        # (e.g. "placed by" vs "shipped by"). It is intentionally ignored
        # here.
        # TODO(pilastro-1-followup): once the EkgBuildStep pipeline (see
        # soup/core/contracts/input.py / future build-step contract)
        # supports typed object-event relationships, use event_objects'
        # qualifier to distinguish them instead of folding every link for
        # a given object_type into a single :CORR edge. Not implemented
        # here by design (out of this session's scope).
        eo_event_idx = event_objects.column_index(_EVENT_ID)
        eo_object_idx = event_objects.column_index(_OBJECT_ID)

        objects_per_event: dict[str, dict[str, list[str]]] = {}
        for row in event_objects.rows:
            event_id, object_id = row[eo_event_idx], row[eo_object_idx]
            obj_type = object_type_by_id.get(object_id)
            if obj_type is None:
                continue  # reference to an object missing from `objects`; silently skipped
            objects_per_event.setdefault(event_id, {}).setdefault(obj_type, []).append(object_id)

        event_id_idx = data.events.column_index(mapping.event_id)
        new_columns = data.events.columns + tuple(object_types)

        new_rows = []
        for row in data.events.rows:
            event_id = row[event_id_idx]
            per_type = objects_per_event.get(event_id, {})
            extra = tuple((",".join(per_type[object_type]) or None) if object_type in per_type else None
                           for object_type in object_types)
            new_rows.append(row + extra)

        events_table = Table(new_columns, tuple(new_rows))

        merged_entity_columns = tuple(dict.fromkeys((*mapping.entity_columns, *object_types)))
        merged_mapping = replace(mapping, entity_columns=merged_entity_columns)

        return events_table, merged_mapping

    @staticmethod
    def _normalize(table: Table, mapping: ColumnMapping) -> tuple[Table, ColumnMapping]:
        """Whitespace normalization, millisecond-comma fix, then mapping validation."""

        normalized_columns = tuple(_normalize_text(column) for column in table.columns)
        normalized_mapping = mapping._normalized()
        normalized_mapping.validate_against(normalized_columns)

        timestamp_index = normalized_columns.index(normalized_mapping.timestamp)

        normalized_rows = []
        for row in table.rows:
            new_row = []
            for index, value in enumerate(row):
                if value is None:
                    new_row.append(None)
                    continue
                cleaned = _normalize_text(value)
                if index == timestamp_index:
                    cleaned = _fix_millis_comma(cleaned)
                new_row.append(cleaned)
            normalized_rows.append(tuple(new_row))

        return Table(normalized_columns, tuple(normalized_rows)), normalized_mapping

    # ------------------------------------------------------------------ #
    # Entity extraction
    # ------------------------------------------------------------------ #
    def entity_table(self) -> Table:
        """
        Distinct (type, value, ...) rows for every entity column,
        splitting multi-valued cells on ',' - consistent with the :CORR
        query's split(e.key, ',') in Utils/graph_query_lib.py. When this
        log came from the separated form, rows sourced from `objects`
        also carry that object's extra attribute columns (if any), and
        objects never referenced by any event are still included;
        flat-form-derived rows carry no extra attributes.
        """

        attribute_columns: tuple[str, ...] = ()
        attributes_by_key: dict[tuple[str, str], dict[str, Optional[str]]] = {}

        if self.objects is not None:
            reserved = {_OBJECT_ID, _OBJECT_TYPE}
            attribute_columns = tuple(c for c in self.objects.columns if c not in reserved)
            obj_id_idx = self.objects.column_index(_OBJECT_ID)
            obj_type_idx = self.objects.column_index(_OBJECT_TYPE)
            attr_indexes = [self.objects.column_index(c) for c in attribute_columns]
            for row in self.objects.rows:
                value, type_ = row[obj_id_idx], row[obj_type_idx]
                attributes_by_key[(type_, value)] = {
                    column: row[idx] for column, idx in zip(attribute_columns, attr_indexes)
                }

        order: list[tuple[str, str]] = []
        seen: dict[tuple[str, str], dict[str, Optional[str]]] = {}

        # Objects first, so isolated objects (referenced by no event) are
        # still included in the entity table.
        for key, attrs in attributes_by_key.items():
            order.append(key)
            seen[key] = attrs

        for column in self.mapping.entity_columns:
            if column not in self.events.columns:
                continue
            index = self.events.column_index(column)
            for row in self.events.rows:
                raw = row[index]
                if not raw:
                    continue
                for value in _split_multi_value(raw):
                    key = (column, value)
                    if key not in seen:
                        order.append(key)
                        seen[key] = {}

        columns = ("type", "value") + attribute_columns
        rows = tuple(
            (entity_type, value) + tuple(seen[(entity_type, value)].get(column) for column in attribute_columns)
            for entity_type, value in order
        )
        return Table(columns, rows)

    # ------------------------------------------------------------------ #
    # Canonical CSV staging (for LOAD CSV)
    # ------------------------------------------------------------------ #
    def events_csv(self) -> bytes:
        """
        Canonical events CSV: event_id, timestamp, activity_name, then
        every other mapped column (entity or value) in their original
        order - exactly what load_event_node_query() in
        Utils/graph_query_lib.py expects (row.event_id, row.timestamp,
        row.activity_name, plus one row.<key> per extra property).
        """

        extra_columns = [
            column
            for column in self.events.columns
            if column not in (self.mapping.event_id, self.mapping.timestamp, self.mapping.activity)
            and (column in self.mapping.entity_columns or column in self.mapping.value_columns)
        ]
        canonical_columns = (EVENT_ID_COLUMN, TIMESTAMP_COLUMN, ACTIVITY_COLUMN, *extra_columns)

        event_idx = self.events.column_index(self.mapping.event_id)
        ts_idx = self.events.column_index(self.mapping.timestamp)
        act_idx = self.events.column_index(self.mapping.activity)
        extra_idx = [self.events.column_index(column) for column in extra_columns]

        rows = [
            (row[event_idx], row[ts_idx], row[act_idx], *(row[i] for i in extra_idx))
            for row in self.events.rows
        ]
        return _write_csv(canonical_columns, rows)

    def entities_csv(self) -> bytes:
        """
        Canonical entities CSV: exactly `value,type` - what
        load_entity_node_query() in Utils/graph_query_lib.py expects
        (MERGE (e:Entity {Value: row.value, Type: row.type})).
        """

        table = self.entity_table()
        value_idx = table.column_index("value")
        type_idx = table.column_index("type")
        rows = [(row[value_idx], row[type_idx]) for row in table.rows]
        return _write_csv(("value", "type"), rows)
