"""
------------------------------------------------------------------------
File : test_event_log_separated_form.py
Description: Tests for the separated (OCEL 2.0-style) input shape -
             merging into the flat shape, and that it produces the exact
             same canonical CSV output as an equivalent flat log.
Project : soup-server
------------------------------------------------------------------------
"""

from soup.core.contracts import EventLogData, Table
from soup.core.event_log import ColumnMapping, EventLog


def _flat_log():
    events = Table(
        ("EventID", "Activity", "Timestamp", "Resource", "Items"),
        (
            ("e1", "Create Order", "2021-05-01T09:05:00.000", "R1", "i1,i2"),
            ("e2", "Place SO", "2021-05-01T11:25:00.000", "R1", "i3"),
        ),
    )
    mapping = ColumnMapping.from_payload(
        ["EventID", "Timestamp", "Activity"],
        filtered_columns=["Items"],
        values_columns=["Resource"],
    )
    return EventLog.from_data(EventLogData(events=events), mapping)


def _separated_log():
    events = Table(
        ("EventID", "Activity", "Timestamp", "Resource"),
        (
            ("e1", "Create Order", "2021-05-01T09:05:00.000", "R1"),
            ("e2", "Place SO", "2021-05-01T11:25:00.000", "R1"),
        ),
    )
    objects = Table(
        ("object_id", "object_type"),
        (("i1", "Items"), ("i2", "Items"), ("i3", "Items")),
    )
    event_objects = Table(
        ("event_id", "object_id"),
        (("e1", "i1"), ("e1", "i2"), ("e2", "i3")),
    )
    mapping = ColumnMapping.from_payload(["EventID", "Timestamp", "Activity"], values_columns=["Resource"])
    data = EventLogData(events=events, objects=objects, event_objects=event_objects)
    return EventLog.from_data(data, mapping)


def test_separated_form_merges_object_type_into_a_comma_joined_column():
    log = _separated_log()
    items_index = log.events.column_index("Items")
    event_id_index = log.events.column_index("EventID")

    by_event = {row[event_id_index]: row[items_index] for row in log.events.rows}
    assert by_event["e1"] == "i1,i2"
    assert by_event["e2"] == "i3"


def test_separated_form_entity_columns_include_synthesized_object_type():
    log = _separated_log()
    assert "Items" in log.mapping.entity_columns


def test_separated_tables_match_flat_form():
    flat_log = _flat_log()
    separated_log = _separated_log()

    assert separated_log.events_csv() == flat_log.events_csv()
    assert separated_log.entities_csv() == flat_log.entities_csv()


def test_object_without_any_linked_event_still_appears_in_entity_table():
    events = Table(("EventID", "Activity", "Timestamp"), (("e1", "Create", "2021-01-01T10:00:00.000"),))
    objects = Table(("object_id", "object_type"), (("o1", "order"), ("o2", "order")))
    event_objects = Table(("event_id", "object_id"), (("e1", "o1"),))  # o2 is never linked

    mapping = ColumnMapping.from_payload(["EventID", "Timestamp", "Activity"])
    log = EventLog.from_data(EventLogData(events=events, objects=objects, event_objects=event_objects), mapping)

    entities = {(row[0], row[1]) for row in log.entity_table().rows}
    assert ("order", "o1") in entities
    assert ("order", "o2") in entities


def test_object_attributes_feed_the_entity_table():
    events = Table(("EventID", "Activity", "Timestamp"), (("e1", "Create", "2021-01-01T10:00:00.000"),))
    objects = Table(
        ("object_id", "object_type", "weight"),
        (("o1", "order", "12"),),
    )
    event_objects = Table(("event_id", "object_id"), (("e1", "o1"),))

    mapping = ColumnMapping.from_payload(["EventID", "Timestamp", "Activity"])
    log = EventLog.from_data(EventLogData(events=events, objects=objects, event_objects=event_objects), mapping)

    table = log.entity_table()
    assert "weight" in table.columns

    weight_index = table.column_index("weight")
    value_index = table.column_index("value")
    row = next(r for r in table.rows if r[value_index] == "o1")
    assert row[weight_index] == "12"

    # but the canonical entities CSV (what LOAD CSV expects today) stays
    # exactly value,type - the extra attribute is not exported (yet).
    assert log.entities_csv() == b"value,type\no1,order\n"


def test_event_objects_qualifier_column_is_ignored_without_error():
    events = Table(("EventID", "Activity", "Timestamp"), (("e1", "Create", "2021-01-01T10:00:00.000"),))
    objects = Table(("object_id", "object_type"), (("o1", "order"),))
    event_objects = Table(("event_id", "object_id", "qualifier"), (("e1", "o1", "placed_by"),))

    mapping = ColumnMapping.from_payload(["EventID", "Timestamp", "Activity"])
    log = EventLog.from_data(EventLogData(events=events, objects=objects, event_objects=event_objects), mapping)

    items_index = log.events.column_index("order")
    assert log.events.rows[0][items_index] == "o1"
