"""
------------------------------------------------------------------------
File : test_event_log_normalization.py
Description: Tests for the normalization pipeline common to every input
             format (soup.core.event_log.EventLog._normalize / from_data).
Project : soup-server
------------------------------------------------------------------------
"""

import pytest

from soup.core.contracts import EventLogData, Table
from soup.core.errors import ValidationError
from soup.core.event_log import ColumnMapping, EventLog


def _flat_data():
    table = Table(
        (" EventID ", "Activity", " Timestamp", "Resource ", "Items"),
        (
            ("e1", " Create Order ", "2021-05-01T09:05:00.000", " R1 ", "i1,i2"),
            ("e2", "Place SO", "2021-05-01T11:25:00,000", "R1", "i3"),
        ),
    )
    return EventLogData(events=table)


def _mapping():
    return ColumnMapping.from_payload(
        [" EventID ", " Timestamp", "Activity"],
        filtered_columns=["Items"],
        values_columns=["Resource "],
    )


def test_normalisation_is_common_to_every_format():
    log = EventLog.from_data(_flat_data(), _mapping())

    # header spaces normalized (also reflected in the resolved mapping)
    assert "EventID" in log.events.columns
    assert "Timestamp" in log.events.columns
    assert "Resource" in log.events.columns
    assert log.mapping.event_id == "EventID"
    assert log.mapping.timestamp == "Timestamp"
    assert log.mapping.activity == "Activity"

    # value spaces normalized ("_Create_Order_" would be the legacy-buggy
    # result of replace-then-trim; stripped-then-collapsed is correct)
    activity_index = log.events.column_index("Activity")
    assert log.events.rows[0][activity_index] == "Create_Order"

    resource_index = log.events.column_index("Resource")
    assert log.events.rows[0][resource_index] == "R1"

    # millisecond comma fixed only in the timestamp column
    timestamp_index = log.events.column_index("Timestamp")
    assert log.events.rows[0][timestamp_index] == "2021-05-01T09:05:00.000"
    assert log.events.rows[1][timestamp_index] == "2021-05-01T11:25:00.000"

    # "i1,i2" splits into two distinct entities
    entities = {(row[0], row[1]) for row in log.entity_table().rows}
    assert ("Items", "i1") in entities
    assert ("Items", "i2") in entities
    assert ("Items", "i3") in entities
    assert len(entities) == 3


def test_mapping_validation_raises_validation_error_with_clear_message():
    data = EventLogData(events=Table(("EventID", "Activity", "Timestamp"), (("e1", "Create", "2021-01-01T10:00:00.000"),)))
    mapping = ColumnMapping.from_payload(["EventID", "Timestamp", "DoesNotExist"])

    with pytest.raises(ValidationError) as exc_info:
        EventLog.from_data(data, mapping)

    assert "DoesNotExist" in str(exc_info.value)


def test_standard_column_mapping_must_have_exactly_three_entries():
    with pytest.raises(ValidationError):
        ColumnMapping.from_payload(["EventID", "Timestamp"])
