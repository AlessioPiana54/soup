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
from soup.core.contracts.errors import ValidationError
from soup.core.registry import Registry
from soup.core.services.import_service import ImportCommand, ImportService
from soup.core.settings import Settings
from tests.fakes import FakeDatabase, InMemoryFileStorage, fake_tool_engine
from tests.packages import bundled_api

CsvEventLogReader = bundled_api("csv_reader").CsvEventLogReader


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
    settings = Settings.from_env({"SOUP_PACKAGES": ",".join(plugins)})
    return fake_tool_engine(settings, db=db or FakeDatabase(), files=storage or InMemoryFileStorage())


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


def test_config_always_includes_process_info_with_the_legacy_shape():
    # Regression test: support.service.ts's parseItemToDataset() reads
    # item['process_info']['init_time'] unconditionally for every dataset
    # in the list, with no null check - a missing "process_info" key
    # crashes the whole datasets page (TypeError: Cannot read properties
    # of undefined (reading 'init_time')), not just this one dataset.
    engine = _engine()

    with open("tests/fixtures/sample_event_log.csv", "rb") as stream:
        command = ImportCommand(
            filename="sample_event_log.csv", stream=stream, kind=EVENT_LOG, options=_fixture_options()
        )
        engine.import_service.import_(command)

    config = engine.repository.load_config("orders")

    assert "process_info" in config
    process_info = config["process_info"]

    # Every key Models/dataset_process_info_model.py's
    # DatasetProcessInformation.to_dict() produces must be present.
    expected_keys = {
        "init_time",
        "finish_time",
        "init_class_time",
        "finish_class_time",
        "init_event_time",
        "finish_event_time",
        "init_entity_time",
        "finish_entity_time",
        "init_corr_time",
        "finish_corr_time",
        "init_df_time",
        "finish_df_time",
        "init_class_node_time",
        "finish_class_node_time",
        "init_obs_time",
        "finish_obs_time",
        "init_dfc_time",
        "finish_dfc_time",
    }
    assert expected_keys.issubset(process_info.keys())

    assert process_info["init_time"] is not None
    assert process_info["finish_time"] is not None
    assert process_info["init_time"] == config["date_created"]
    assert process_info["finish_time"] == config["date_modified"]


def test_config_uses_normalized_column_names_not_the_raw_request_ones():
    # _fixture_options() all_columns includes " Order_Id" (leading space) -
    # the graph is built with the normalized "Order_Id", and the legacy
    # code that still reads this config (filters) looks columns up by that
    # same normalized name.
    engine = _engine()

    with open("tests/fixtures/sample_event_log.csv", "rb") as stream:
        command = ImportCommand(
            filename="sample_event_log.csv", stream=stream, kind=EVENT_LOG, options=_fixture_options()
        )
        engine.import_service.import_(command)

    config = engine.repository.load_config("orders")

    assert "Order_Id" in config["all_columns"]
    assert " Order_Id" not in config["all_columns"]

    assert config["filtered_columns"] == ["Items"]
    assert config["values_columns"] == ["Resource"]


def test_config_standard_columns_matches_the_canonical_csv_header_not_the_mapping():
    # Regression test: GenericGraphService.create_complete_graphs_s (legacy
    # /complete-graph/build, still called every time a dataset is selected
    # from the list) uses config["standard_columns"] as literal Cypher
    # property names against the canonical events CSV. That CSV always
    # writes the fixed "event_id"/"timestamp"/"activity_name" headers for
    # the standard roles (EventLog.events_csv), regardless of what the
    # original request's column names were ("EventID"/"Timestamp"/
    # "Activity" here) - so standard_columns must store those fixed names,
    # not the request's mapping names, or the rebuild endpoint fails to
    # find any matching column and returns a non-'success' result.
    engine = _engine()

    with open("tests/fixtures/sample_event_log.csv", "rb") as stream:
        command = ImportCommand(
            filename="sample_event_log.csv", stream=stream, kind=EVENT_LOG, options=_fixture_options()
        )
        engine.import_service.import_(command)

    config = engine.repository.load_config("orders")

    assert config["standard_columns"] == ["event_id", "timestamp", "activity_name"]


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
