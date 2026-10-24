"""
------------------------------------------------------------------------
File : test_csv_reader.py
Description: Tests for the csv_reader plugin (soup-packages/csv_reader):
             dtype=str correctness on the fixture CSV, and that it is
             registered under the csv_reader plugin with kind event_log.
Project : soup-server
------------------------------------------------------------------------
"""

from soup.core.contracts import EVENT_LOG
from soup.core.engine import build_engine
from soup.core.settings import Settings
from tests.fakes import FakeDatabase, InMemoryFileStorage
from tests.packages import bundled_api

CsvEventLogReader = bundled_api("csv_reader").CsvEventLogReader


def _read_fixture():
    reader = CsvEventLogReader()
    with open("tests/fixtures/sample_event_log.csv", "rb") as stream:
        return reader.read(stream)


def test_reader_kind_and_format():
    reader = CsvEventLogReader()
    assert reader.kind == EVENT_LOG
    assert reader.format_id == "csv"
    assert reader.accepts("order_process.csv")
    assert not reader.accepts("order_process.json")


def test_integer_id_with_empty_cell_is_not_turned_into_a_float():
    data = _read_fixture()
    table = data.events
    order_id_index = table.column_index(" Order_Id")

    first_row = table.rows[0]
    assert first_row[order_id_index] == "1"  # not "1.0"

    # a row with an empty Order_Id cell is read as None, not NaN/float
    empty_values = [row[order_id_index] for row in table.rows if row[order_id_index] is None]
    assert len(empty_values) >= 1


def test_multi_value_entity_cell_is_read_intact():
    data = _read_fixture()
    table = data.events
    items_index = table.column_index("Items")

    first_row = table.rows[0]
    assert first_row[items_index] == "i1,i2"


def test_csv_reader_is_registered_by_csv_reader_plugin():
    settings = Settings.from_env({})  # default plugins include csv_reader
    engine = build_engine(settings, db=FakeDatabase(), storage=InMemoryFileStorage())

    assert "csv_reader" in engine.report.loaded
    assert engine.report.failed == []

    reader = engine.ctx.input_readers.get("csv")
    assert reader is not None
    assert reader.kind == EVENT_LOG
    assert engine.ctx.input_readers.owner_of("csv") == "csv_reader"
