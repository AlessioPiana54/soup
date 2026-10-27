"""
------------------------------------------------------------------------
File : test_event_log_canonical_csv.py
Description: Tests that EventLog.events_csv()/entities_csv() produce
             exactly the columns the current LOAD CSV queries expect
             (Utils/graph_query_lib.py, not modified by this session):
             - load_event_node_query(): row.<event_id_col>,
               row.<timestamp_col>, row.<activity_col>, plus one
               row.<key> per extra property (cypher_properties built in
               Services/generic_graph_service.py).
             - load_entity_node_query(): row.value, row.type.
Project : soup-packages/ekg
------------------------------------------------------------------------
"""

import csv
import io

from tests.packages import bundled_api, bundled_module

_api = bundled_api("ekg")
ColumnMapping, EventLog, EventLogData, Table = _api.ColumnMapping, _api.EventLog, _api.EventLogData, _api.Table
_event_log = bundled_module("ekg", "event_log")
ACTIVITY_COLUMN, EVENT_ID_COLUMN, TIMESTAMP_COLUMN = (
    _event_log.ACTIVITY_COLUMN, _event_log.EVENT_ID_COLUMN, _event_log.TIMESTAMP_COLUMN,
)


def _log():
    events = Table(
        ("EventID", "Activity", "Timestamp", "Resource", "Items"),
        (("e1", "Create Order", "2021-05-01T09:05:00.000", "R1", "i1,i2"),),
    )
    mapping = ColumnMapping.from_payload(
        ["EventID", "Timestamp", "Activity"],
        filtered_columns=["Items"],
        values_columns=["Resource"],
    )
    return EventLog.from_data(EventLogData(events=events), mapping)


def test_events_csv_has_the_three_standard_columns_load_event_node_query_expects():
    log = _log()
    reader = csv.reader(io.StringIO(log.events_csv().decode("utf-8")))
    header = next(reader)

    assert header[0] == EVENT_ID_COLUMN == "event_id"
    assert header[1] == TIMESTAMP_COLUMN == "timestamp"
    assert header[2] == ACTIVITY_COLUMN == "activity_name"


def test_events_csv_includes_extra_properties_by_their_own_column_name():
    # cypher_properties in generic_graph_service.py references extra
    # columns by their original name via row.<key> - the canonical CSV
    # must keep that exact name as a header.
    log = _log()
    reader = csv.reader(io.StringIO(log.events_csv().decode("utf-8")))
    header = next(reader)

    assert "Resource" in header
    assert "Items" in header


def test_entities_csv_has_exactly_value_and_type_columns():
    log = _log()
    reader = csv.reader(io.StringIO(log.entities_csv().decode("utf-8")))
    header = next(reader)

    assert header == ["value", "type"]


def test_entities_csv_rows_match_load_entity_node_query_shape():
    log = _log()
    reader = csv.reader(io.StringIO(log.entities_csv().decode("utf-8")))
    next(reader)  # header
    rows = {tuple(row) for row in reader}

    assert ("i1", "Items") in rows
    assert ("i2", "Items") in rows
