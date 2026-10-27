"""
------------------------------------------------------------------------
File : test_csv_ekg_reader.py
Description: Tests for the CSV reading of csv_ekg (moved from
             soup-server/tests/test_csv_reader.py, the csv_reader
             package being gone): dtype=str correctness on the fixture
             CSV, multi-valued cells read intact, and the importer
             registered by the csv_ekg package for .csv files, producing
             "ekg" objects, next to csv_table's.
Project : soup-packages/csv_ekg
------------------------------------------------------------------------
"""

import pytest

from soup.core.contracts import ValidationError
from tests.fakes import ekg_engine
from tests.packages import bundled_api

csv_ekg = bundled_api("csv_ekg")


def _read_fixture(path):
    with open(path, "rb") as stream:
        return csv_ekg.read_csv(stream)


def test_importer_kind_and_extensions():
    importer = csv_ekg.CsvEkgImporter()
    assert (importer.id, importer.produces, csv_ekg.FORMAT_ID) == ("csv", "ekg", "csv")
    assert importer.label == "CSV come event log (EKG su Memgraph)"
    assert importer.accepts("order_process.csv")
    assert not importer.accepts("order_process.json")
    assert set(importer.requires_tools) == {"memgraph", "storage"}


def test_integer_id_with_empty_cell_is_not_turned_into_a_float(sample_event_log_csv):
    table = _read_fixture(sample_event_log_csv).events
    order_id_index = table.column_index(" Order_Id")

    first_row = table.rows[0]
    assert first_row[order_id_index] == "1"  # not "1.0"

    # a row with an empty Order_Id cell is read as None, not NaN/float
    empty_values = [row[order_id_index] for row in table.rows if row[order_id_index] is None]
    assert len(empty_values) >= 1


def test_multi_value_entity_cell_is_read_intact(sample_event_log_csv):
    table = _read_fixture(sample_event_log_csv).events
    items_index = table.column_index("Items")

    first_row = table.rows[0]
    assert first_row[items_index] == "i1,i2"


def test_an_unreadable_file_is_a_validation_error():
    import io

    with pytest.raises(ValidationError):
        csv_ekg.read_csv(io.BytesIO(b""))


def test_with_a_csv_both_csv_ekg_and_csv_table_are_offered(tmp_path, monkeypatch):
    engine = ekg_engine(tmp_path, monkeypatch)

    assert engine.report.failed == []
    entries = engine.import_router.importers_for("orders.csv")
    assert [(entry.key, entry.package, entry.item.produces) for entry in entries] == [
        ("csv_ekg.csv", "csv_ekg", "ekg"),
        ("csv_table.csv", "csv_table", "table"),
    ]
    # .tsv is csv_table's only.
    assert [entry.key for entry in engine.import_router.importers_for("orders.tsv")] == ["csv_table.csv"]
