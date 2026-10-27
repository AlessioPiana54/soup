"""
------------------------------------------------------------------------
File : test_event_log_data.py
Description: Tests for EventLogData (ekg package, event_log.py; moved
             from soup-server/tests).
Project : soup-packages/ekg
------------------------------------------------------------------------
"""

import pytest

from tests.packages import bundled_api

EventLogData = bundled_api("ekg").EventLogData
Table = bundled_api("ekg").Table


def _events_table():
    return Table(("EventID", "Activity", "Timestamp"), (("e1", "Create", "2021-01-01T10:00:00.000"),))


def test_flat_form_only_needs_events():
    data = EventLogData(events=_events_table())
    assert data.objects is None
    assert data.event_objects is None


def test_separated_form_accepts_valid_objects_and_event_objects():
    objects = Table(("object_id", "object_type"), (("o1", "order"),))
    event_objects = Table(("event_id", "object_id"), (("e1", "o1"),))

    data = EventLogData(events=_events_table(), objects=objects, event_objects=event_objects)
    assert data.objects is objects
    assert data.event_objects is event_objects


def test_separated_form_accepts_optional_qualifier_column():
    objects = Table(("object_id", "object_type"), (("o1", "order"),))
    event_objects = Table(("event_id", "object_id", "qualifier"), (("e1", "o1", "placed"),))

    data = EventLogData(events=_events_table(), objects=objects, event_objects=event_objects)
    assert "qualifier" in data.event_objects.columns


def test_objects_without_object_id_is_rejected():
    objects = Table(("object_type",), (("order",),))
    with pytest.raises(ValueError):
        EventLogData(events=_events_table(), objects=objects)


def test_objects_without_object_type_is_rejected():
    objects = Table(("object_id",), (("o1",),))
    with pytest.raises(ValueError):
        EventLogData(events=_events_table(), objects=objects)


def test_event_objects_without_event_id_is_rejected():
    objects = Table(("object_id", "object_type"), (("o1", "order"),))
    event_objects = Table(("object_id",), (("o1",),))  # missing event_id

    with pytest.raises(ValueError):
        EventLogData(events=_events_table(), objects=objects, event_objects=event_objects)


def test_event_objects_without_object_id_is_rejected():
    objects = Table(("object_id", "object_type"), (("o1", "order"),))
    event_objects = Table(("event_id",), (("e1",),))  # missing object_id

    with pytest.raises(ValueError):
        EventLogData(events=_events_table(), objects=objects, event_objects=event_objects)
