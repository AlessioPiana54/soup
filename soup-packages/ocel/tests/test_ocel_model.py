"""
------------------------------------------------------------------------
File : test_ocel_model.py
Description: Tests for the OCEL 2.0 model of the ocel package (model.py,
             and the conversion of graph.py): the small log of
             tests/fixtures/orders.json parsed, kept as tables and
             rebuilt unchanged, written back as OCEL 2.0 JSON; the types
             derived when the file does not declare them; every kind of
             non-conforming file refused with a ValidationError that says
             where; the separated EventLogData for the ekg package, with
             the times in UTC and the attributes renamed away from the
             reserved names and the object types; parse_time with "Z",
             offsets, naive times and milliseconds; a null attribute kept
             null from the file to the export.
Project : soup-packages/ocel
------------------------------------------------------------------------
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from soup.core.contracts import ValidationError
from tests.packages import bundled_module

model = bundled_module("ocel", "model")
graph = bundled_module("ocel", "graph")

FIXTURE = Path(__file__).parent / "fixtures" / "orders.json"


def _document():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _bytes(document) -> bytes:
    return json.dumps(document).encode("utf-8")


@pytest.fixture
def log():
    return model.parse(FIXTURE.read_bytes())


def test_the_fixture_is_parsed_with_its_counts_and_types(log):
    assert log.counts() == {
        "events": 5, "objects": 6, "event_types": 3, "object_types": 3, "event_objects": 12, "object_objects": 4,
    }
    assert log.events_per_type() == {"place order": 2, "pick item": 2, "pay order": 1}
    assert log.objects_per_type() == {"order": 2, "item": 3, "customer": 1}
    assert [decl.name for decl in log.object_types] == ["order", "item", "customer"]
    assert log.events[0].relationships[1] == model.Relationship("c1", "customer")


def test_the_tables_keep_the_qualifiers_and_the_first_value_of_each_object_attribute(log):
    tables = model.to_tables(log)

    assert set(tables) == set(model.TABLES)
    events = tables[model.EVENTS]
    assert events.columns == ("event_id", "event_type", "time", "resource", "amount")
    assert events.rows[4] == ("e5", "pay order", "2023-01-03T12:00:00Z", None, 12.0)
    objects = tables[model.OBJECTS]
    assert objects.columns == ("object_id", "object_type", "total", "weight", "name")
    # o1's total is 10.5 at the start and 12.0 later: the table shows the first.
    assert objects.rows[0] == ("o1", "order", 10.5, None, None)
    assert tables[model.EVENT_OBJECTS].rows[0] == ("e1", "place order", "o1", "order", "order")
    assert ("o1", "order", "c1", "customer", "ordered by") in tables[model.OBJECT_OBJECTS].rows
    assert tables[model.OBJECT_ATTRIBUTES].rows[:2] == (
        ("o1", "total", "1970-01-01T00:00:00Z", 10.5), ("o1", "total", "2023-01-01T11:00:00Z", 12.0),
    )


def test_the_log_is_rebuilt_unchanged_from_the_stored_tables(log):
    stored = {name: model.StoredTable.from_json(table.to_json()) for name, table in model.to_tables(log).items()}
    types = json.loads(json.dumps(model.types_document(log)))

    assert model.from_tables(stored, types) == log


def test_the_json_document_parses_back_to_the_same_log(log):
    document = model.to_json(log)

    assert set(document) == {"eventTypes", "objectTypes", "objects", "events"}
    assert model.parse(_bytes(document)) == log
    assert document["objects"][0]["attributes"][1] == {"name": "total", "time": "2023-01-01T11:00:00Z", "value": 12.0}


def test_without_declared_types_they_come_from_the_events_and_objects():
    document = _document()
    del document["eventTypes"], document["objectTypes"]

    log = model.parse(_bytes(document))

    assert [decl.name for decl in log.event_types] == ["place order", "pick item", "pay order"]
    assert log.event_types[2].attributes == (("amount", "float"),)
    assert [decl.name for decl in log.object_types] == ["order", "item", "customer"]
    assert log.object_types[0].attributes == (("total", "float"),)


def test_an_attribute_named_like_a_fixed_column_gets_a_suffix_in_the_table():
    document = _document()
    document["events"][0]["attributes"].append({"name": "time", "value": "late"})

    events = model.to_tables(model.parse(_bytes(document)))[model.EVENTS]

    assert events.columns == ("event_id", "event_type", "time", "resource", "amount", "time_2")
    assert events.attributes == ("resource", "amount", "time")
    assert events.rows[0][-1] == "late"


def _broken(change):
    document = _document()
    change(document)
    return _bytes(document)


def _set(path, value):
    def change(document):
        target = document
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
    return change


@pytest.mark.parametrize("data, message", [
    (b"{not json", "not JSON (line 1, column 2"),
    (b"\xff\xfe\x00", "not UTF-8"),
    (b"[]", "must be a JSON object with 'events' and 'objects', got a list"),
    (_broken(lambda d: d.pop("events")), "missing 'events'"),
    (_broken(_set(["objects"], {})), "objects: must be a list, got an object"),
    (_broken(_set(["events", 1], "e2")), "events[1]: must be a JSON object, got a string"),
    (_broken(lambda d: d["events"][2].pop("time")), "events[2].time: must be a non-empty string"),
    (_broken(_set(["events", 2, "time"], "yesterday")), "events[2].time: 'yesterday' is not an ISO 8601"),
    (_broken(_set(["events", 3, "id"], "e1")), "events[3].id: event 'e1' appears twice"),
    (_broken(_set(["objects", 5, "id"], "o1")), "objects[5].id: object 'o1' appears twice"),
    (_broken(_set(["events", 0, "type"], "ship")), "events[0].type: type 'ship' is not declared in 'eventTypes'"),
    (_broken(_set(["objects", 0, "type"], "truck")), "objects[0].type: type 'truck' is not declared in 'objectTypes'"),
    (_broken(_set(["events", 0, "relationships", 1, "objectId"], "c9")),
     "events[0].relationships[1].objectId: object 'c9' is not among the objects"),
    (_broken(_set(["objects", 0, "relationships", 0, "objectId"], "i9")),
     "objects[0].relationships[0].objectId: object 'i9' is not among the objects"),
    (_broken(_set(["events", 0, "attributes", 0, "value"], {"nested": 1})),
     "events[0].attributes[0].value: must be a string, a number or a boolean, got an object"),
    (_broken(_set(["objects", 0, "attributes", 1, "time"], "soon")), "objects[0].attributes[1].time: 'soon'"),
    (_broken(lambda d: d["eventTypes"].append({"name": "pay order"})), "eventTypes[3]: type 'pay order' is declared twice"),
])
def test_a_non_conforming_file_is_refused_saying_where(data, message):
    with pytest.raises(ValidationError) as exc_info:
        model.parse(data)

    assert str(exc_info.value).startswith("Not a valid OCEL 2.0 JSON file: ")
    assert message in str(exc_info.value)
    assert exc_info.value.http_status_code == 400


def test_the_event_log_data_is_the_separated_form_with_a_fixed_mapping(log):
    data, mapping = graph.event_log_data(log)

    assert (mapping.event_id, mapping.timestamp, mapping.activity) == ("ocel:eid", "ocel:timestamp", "ocel:activity")
    assert mapping.entity_columns == ()
    assert mapping.value_columns == ("resource", "amount")
    assert data.events.columns == ("ocel:eid", "ocel:activity", "ocel:timestamp", "resource", "amount")
    # 10:30 at +01:00 is 09:30 UTC; numbers become text.
    assert data.events.rows[1] == ("e2", "place order", "2023-01-01T09:30:00.000", "Bob", None)
    assert data.events.rows[4][-1] == "12.0"
    assert data.objects.rows[0] == ("o1", "order")
    assert len(data.event_objects.rows) == 12
    assert data.event_objects.rows[0] == ("e1", "o1", "order")


def test_graph_times_are_utc_without_offset():
    assert graph.graph_time("2023-01-01T10:30:00+01:00") == "2023-01-01T09:30:00.000"
    assert graph.graph_time("2023-01-01T10:30:00Z") == "2023-01-01T10:30:00.000"
    assert graph.graph_time("2023-01-01T10:30:00.123456") == "2023-01-01T10:30:00.123"


def test_attributes_never_take_a_reserved_name_or_the_name_of_an_object_type():
    document = _document()
    document["events"][0]["attributes"] += [
        {"name": "customer", "value": "Ada"},
        {"name": "Timestamp", "value": "x"},
        {"name": "customer_attribute", "value": "y"},
    ]

    columns = graph.attribute_columns(model.parse(_bytes(document)))

    assert columns == {
        "resource": "resource",
        "amount": "amount",
        "customer": "customer_attribute",
        "Timestamp": "Timestamp_attribute",
        "customer_attribute": "customer_attribute_attribute",
    }


# ---------------------------------------------------------------------- #
# Times ("Z" on every Python version) and null values
# ---------------------------------------------------------------------- #
@pytest.mark.parametrize("text, expected", [
    ("2021-05-01T09:05:00Z", datetime(2021, 5, 1, 9, 5, tzinfo=timezone.utc)),
    ("2021-05-01T09:05:00z", datetime(2021, 5, 1, 9, 5, tzinfo=timezone.utc)),
    ("2021-05-01T09:05:00+02:00", datetime(2021, 5, 1, 9, 5, tzinfo=timezone(timedelta(hours=2)))),
    ("2021-05-01T09:05:00", datetime(2021, 5, 1, 9, 5)),
    ("2021-05-01T09:05:00.250Z", datetime(2021, 5, 1, 9, 5, 0, 250000, tzinfo=timezone.utc)),
    ("2021-05-01T09:05:00.250", datetime(2021, 5, 1, 9, 5, 0, 250000)),
])
def test_parse_time_reads_utc_offsets_naive_times_and_milliseconds(text, expected):
    assert model.parse_time(text) == expected
    assert model.parse_time(text).utcoffset() == expected.utcoffset()


@pytest.mark.parametrize("text", ["2021-05-01T09:05:00ZZ", "Z", "yesterday", ""])
def test_parse_time_refuses_what_is_not_an_iso_time(text):
    with pytest.raises(ValueError):
        model.parse_time(text)


@pytest.mark.parametrize("text, expected", [
    ("2021-05-01T09:05:00Z", "2021-05-01T09:05:00.000"),
    ("2021-05-01T09:05:00+02:00", "2021-05-01T07:05:00.000"),
    ("2021-05-01T09:05:00", "2021-05-01T09:05:00.000"),
    ("2021-05-01T09:05:00.250Z", "2021-05-01T09:05:00.250"),
])
def test_the_decomposition_reads_every_kind_of_time(text, expected):
    assert graph.graph_time(text) == expected


def test_an_attribute_given_as_null_stays_null_through_tables_and_export(log):
    # e4's resource and i3's weight are null in the fixture.
    assert log.events[3].attributes == (("resource", None),)
    assert log.objects[4].attributes == (("weight", "1970-01-01T00:00:00Z", None),)

    stored = {name: model.StoredTable.from_json(table.to_json()) for name, table in model.to_tables(log).items()}
    assert stored[model.EVENTS].nulls == ((3, 0),)
    rebuilt = model.from_tables(stored, json.loads(json.dumps(model.types_document(log))))
    document = model.to_json(rebuilt)

    assert document["events"][3]["attributes"] == [{"name": "resource", "value": None}]
    # An attribute the event does not have is still left out (e5 has no resource).
    assert document["events"][4]["attributes"] == [{"name": "amount", "value": 12.0}]
    assert document["objects"][4]["attributes"] == [{"name": "weight", "time": "1970-01-01T00:00:00Z", "value": None}]
    assert document["events"] == _document()["events"]
    assert model.parse(_bytes(document)) == log
