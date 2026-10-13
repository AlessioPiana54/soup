"""
------------------------------------------------------------------------
File : test_import_service.py
Description: Tests for ImportService/ImportCommand/EventLogHandler -
             reader/handler dispatch errors, a full end-to-end import
             with FakeDatabase + InMemoryFileStorage, and the
             compensating delete when the EKG build fails.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import io
import json

import pytest

from soup.core.contracts import EVENT_LOG, EventLogData, InputHandler, Table
from soup.core.engine import build_engine
from soup.core.errors import ValidationError
from soup.core.registry import Registry
from soup.core.services.import_service import ImportCommand, ImportService
from soup.core.settings import Settings
from soup.plugins.csv_reader import CsvEventLogReader
from tests.fakes import FakeDatabase, InMemoryFileStorage


def _fixture_options():
    return {
        "dataset_name": "orders",
        "dataset_description": "desc",
        "all_columns": [" EventID ", "Activity", " Timestamp", "Resource ", " Order_Id", "Items"],
        "standard_columns": [" EventID ", " Timestamp", "Activity"],
        "filtered_columns": ["Items"],
        "values_columns": ["Resource "],
        "trigger_target_rows": [],
    }


def _engine(db=None, storage=None, plugins=("csv_reader",)):
    settings = Settings.from_env({"SOUP_PLUGINS": ",".join(plugins)})
    return build_engine(settings, db=db or FakeDatabase(), storage=storage or InMemoryFileStorage())


# ---------------------------------------------------------------------- #
# reader_for() dispatch
# ---------------------------------------------------------------------- #

def test_unsupported_extension_raises_validation_error_with_supported_extensions():
    readers: Registry = Registry("input_reader")
    readers.register(CsvEventLogReader(), "csv_reader", "csv")
    service = ImportService(readers, Registry("input_handler"))

    with pytest.raises(ValidationError) as exc_info:
        service.reader_for("data.txt")

    assert ".csv" in str(exc_info.value)


def test_two_readers_on_the_same_extension_without_kind_raises_explicit_error():
    class _OtherCsvReader(CsvEventLogReader):
        format_id = "csv-alt"

    readers: Registry = Registry("input_reader")
    readers.register(CsvEventLogReader(), "csv_reader", "csv")
    readers.register(_OtherCsvReader(), "other_plugin", "csv-alt")
    service = ImportService(readers, Registry("input_handler"))

    with pytest.raises(ValidationError) as exc_info:
        service.reader_for("data.csv")

    message = str(exc_info.value)
    assert "csv" in message and "csv-alt" in message


def test_kind_disambiguates_between_readers_on_the_same_extension():
    class _OtherKindReader(CsvEventLogReader):
        format_id = "csv-alt"
        kind = "something_else"

    readers: Registry = Registry("input_reader")
    readers.register(CsvEventLogReader(), "csv_reader", "csv")
    readers.register(_OtherKindReader(), "other_plugin", "csv-alt")
    service = ImportService(readers, Registry("input_handler"))

    reader = service.reader_for("data.csv", kind=EVENT_LOG)
    assert reader.format_id == "csv"


def test_no_handler_for_kind_raises_explicit_error():
    readers: Registry = Registry("input_reader")
    readers.register(CsvEventLogReader(), "csv_reader", "csv")
    service = ImportService(readers, Registry("input_handler"))  # no handlers registered

    command = ImportCommand(filename="data.csv", stream=io.BytesIO(b"a,b\n1,2\n"), kind=EVENT_LOG)
    with pytest.raises(ValidationError) as exc_info:
        service.import_(command)

    assert EVENT_LOG in str(exc_info.value)


# ---------------------------------------------------------------------- #
# End-to-end import
# ---------------------------------------------------------------------- #

def test_full_import_with_fake_database_and_in_memory_storage():
    db = FakeDatabase()
    storage = InMemoryFileStorage()
    engine = _engine(db=db, storage=storage)

    with open("tests/fixtures/sample_event_log.csv", "rb") as stream:
        command = ImportCommand(
            filename="sample_event_log.csv", stream=stream, kind=EVENT_LOG, options=_fixture_options()
        )
        result = engine.import_service.import_(command)

    assert result.http_status_code == 201
    assert result.message == "Create graph successfully"

    # CSV loaded from /soup/<name>/<name>.csv (Services/generic_graph_service.py's layout)
    assert storage.exists("orders/orders.csv")
    assert storage.exists("orders/orders_entity.csv")

    load_queries = [q for q in db.received_queries if q.text.startswith("LOAD CSV FROM")]
    assert any("/soup/orders/orders.csv" in q.text for q in load_queries)
    assert any("/soup/orders/orders_entity.csv" in q.text for q in load_queries)

    config = engine.repository.load_config("orders")
    assert config["source_format"] == "csv"
    assert config["date_created"] is not None


def test_failed_build_removes_the_staged_dataset():
    class _ExplodingDatabase(FakeDatabase):
        def run(self, query):
            if query.text.startswith("LOAD CSV"):
                raise RuntimeError("Memgraph is unreachable")
            return super().run(query)

    db = _ExplodingDatabase()
    storage = InMemoryFileStorage()
    engine = _engine(db=db, storage=storage)

    with open("tests/fixtures/sample_event_log.csv", "rb") as stream:
        command = ImportCommand(
            filename="sample_event_log.csv", stream=stream, kind=EVENT_LOG, options=_fixture_options()
        )
        with pytest.raises(RuntimeError):
            engine.import_service.import_(command)

    assert engine.repository.exists("orders") is False
    assert storage.exists("orders/orders.csv") is False
    assert storage.list("orders/") == []
