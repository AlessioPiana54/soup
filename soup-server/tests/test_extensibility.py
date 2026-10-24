"""
------------------------------------------------------------------------
File : test_extensibility.py
Description: Proves the plugin system is actually extensible WITHOUT
             touching soup/core: every plugin here is defined inside this
             test file and wired up only through public contracts
             (SoupPlugin, PluginContext, InputReader/InputHandler,
             Table.from_records) and public services (PluginManager,
             DatasetRepository, EkgService, EventLogHandler, ImportService) -
             the exact same classes a real package in soup-packages/ would use.

             - a flat JSON Lines reader, built with Table.from_records;
             - an OCEL 2.0-style reader producing separated
               events/objects/event_objects tables, and the entities/
               correlations EventLog.from_data is expected to derive
               from them;
             - a reader+handler pair for an entirely new kind
               ("process_model"): the handler is invoked and the
               event-log pipeline (DatasetRepository/EkgService) never
               runs.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import csv
import io
import json

from soup.core.contracts import (
    EVENT_LOG,
    EventLogData,
    EventLogReader,
    InputHandler,
    InputReader,
    PluginContext,
    SoupPlugin,
    Table,
)
from soup.core.dataset_repository import DatasetRepository
from soup.core.plugin_context import DefaultPluginContext
from soup.core.plugin_manager import PluginManager
from soup.core.results import Result
from soup.core.services.ekg_service import EkgService
from soup.core.services.event_log_handler import EventLogHandler
from soup.core.services.import_service import ImportCommand, ImportService
from tests.fakes import FakeDatabase, InMemoryFileStorage


def _build_import_service(plugins, db, storage):
    """
    Mirrors what soup.core.engine.build_engine does, so a test plugin is
    wired up exactly the way a real package in soup-packages/ would be -
    without going through build_engine's string-based plugin discovery
    (which is tested separately in test_plugin_manager.py/test_csv_reader.py).
    """

    manager = PluginManager()
    ctx = DefaultPluginContext()
    report = manager.load(plugins, ctx=ctx)
    assert report.failed == [], report.failed

    repository = DatasetRepository(storage, root="/soup")
    ekg_service = EkgService(db, plugin_build_steps=ctx.build_steps)
    ctx.input_handlers.register(EventLogHandler(repository, ekg_service), owner="core", key=EVENT_LOG)

    return ImportService(ctx.input_readers, ctx.input_handlers), repository


def _read_csv_rows(text: str) -> list[list[str]]:
    reader = csv.reader(io.StringIO(text))
    return list(reader)


# ---------------------------------------------------------------------- #
# 1. Flat JSON Lines reader, built with Table.from_records
# ---------------------------------------------------------------------- #

class _JsonLinesEventLogReader(EventLogReader):
    format_id = "jsonl"
    label = "JSON Lines"
    extensions = (".jsonl",)

    def read(self, stream):
        lines = stream.read().decode("utf-8").splitlines()
        records = [json.loads(line) for line in lines if line.strip()]
        return EventLogData(events=Table.from_records(records))


class _JsonLinesReaderPlugin(SoupPlugin):
    name = "jsonl_reader_test_plugin"
    version = "1.0.0"

    def register(self, ctx: PluginContext) -> None:
        ctx.add_input_reader("jsonl", _JsonLinesEventLogReader())


def test_extensibility_jsonl_flat_reader_built_with_table_from_records():
    db = FakeDatabase()
    storage = InMemoryFileStorage()
    import_service, _repository = _build_import_service([_JsonLinesReaderPlugin()], db, storage)

    jsonl_content = "\n".join([
        json.dumps({"EventID": "e1", "Activity": "Create", "Timestamp": "2021-01-01T10:00:00.000", "Items": "i1,i2"}),
        json.dumps({"EventID": "e2", "Activity": "Ship", "Timestamp": "2021-01-01T11:00:00.000", "Items": "i1"}),
    ])
    stream = io.BytesIO(jsonl_content.encode("utf-8"))

    command = ImportCommand(
        filename="log.jsonl",
        stream=stream,
        kind=EVENT_LOG,
        options={
            "dataset_name": "jsonl_ds",
            "standard_columns": ["EventID", "Timestamp", "Activity"],
            "filtered_columns": ["Items"],
        },
    )
    result = import_service.import_(command)

    assert result.http_status_code == 201

    rows = _read_csv_rows(storage.read("jsonl_ds/jsonl_ds.csv").decode("utf-8"))
    assert rows[0] == ["event_id", "timestamp", "activity_name", "Items"]
    assert ["e1", "2021-01-01T10:00:00.000", "Create", "i1,i2"] in rows


# ---------------------------------------------------------------------- #
# 2. OCEL 2.0-style reader (separated events/objects/event_objects)
# ---------------------------------------------------------------------- #

class _OcelLikeReader(EventLogReader):
    format_id = "ocel"
    label = "OCEL 2.0-like"
    extensions = (".ocel.json",)

    def accepts(self, filename: str) -> bool:
        return filename.lower().endswith(".ocel.json")

    def read(self, stream):
        payload = json.loads(stream.read().decode("utf-8"))
        return EventLogData(
            events=Table.from_records(payload["events"]),
            objects=Table.from_records(payload["objects"]),
            event_objects=Table.from_records(payload["event_objects"]),
        )


class _OcelReaderPlugin(SoupPlugin):
    name = "ocel_reader_test_plugin"
    version = "1.0.0"

    def register(self, ctx: PluginContext) -> None:
        ctx.add_input_reader("ocel", _OcelLikeReader())


def test_extensibility_ocel_style_separated_reader_produces_expected_entities_and_correlations():
    db = FakeDatabase()
    storage = InMemoryFileStorage()
    import_service, _repository = _build_import_service([_OcelReaderPlugin()], db, storage)

    payload = {
        "events": [
            {"EventID": "e1", "Activity": "Create", "Timestamp": "2021-01-01T10:00:00.000"},
            {"EventID": "e2", "Activity": "Ship", "Timestamp": "2021-01-01T11:00:00.000"},
        ],
        "objects": [
            {"object_id": "o1", "object_type": "order"},
            {"object_id": "o2", "object_type": "order"},
        ],
        "event_objects": [
            {"event_id": "e1", "object_id": "o1"},
            {"event_id": "e1", "object_id": "o2"},
            {"event_id": "e2", "object_id": "o1"},
        ],
    }
    stream = io.BytesIO(json.dumps(payload).encode("utf-8"))

    command = ImportCommand(
        filename="log.ocel.json",
        stream=stream,
        kind=EVENT_LOG,
        options={"dataset_name": "ocel_ds", "standard_columns": ["EventID", "Timestamp", "Activity"]},
    )
    result = import_service.import_(command)
    assert result.http_status_code == 201

    # entities: both order objects, even though o2 only ever appears via
    # event_objects (never as an events-table column, since this is the
    # separated form)
    entity_rows = _read_csv_rows(storage.read("ocel_ds/ocel_ds_entity.csv").decode("utf-8"))
    assert entity_rows[0] == ["value", "type"]
    assert ["o1", "order"] in entity_rows
    assert ["o2", "order"] in entity_rows

    # correlation: the synthesized "order" column comma-joins e1's two
    # linked objects, in event_objects order
    event_rows = _read_csv_rows(storage.read("ocel_ds/ocel_ds.csv").decode("utf-8"))
    header = event_rows[0]
    assert "order" in header
    order_index = header.index("order")
    e1_row = next(row for row in event_rows[1:] if row[0] == "e1")
    e2_row = next(row for row in event_rows[1:] if row[0] == "e2")
    assert e1_row[order_index] == "o1,o2"
    assert e2_row[order_index] == "o1"

    # the corresponding :CORR query ran for the synthesized "order" type
    corr_queries = [q for q in db.received_queries if q.params.get("entity_type") == "order"]
    assert len(corr_queries) >= 1


# ---------------------------------------------------------------------- #
# 3. A brand-new kind ("process_model"): its handler runs, the event-log
#    pipeline (DatasetRepository/EkgService) never does.
# ---------------------------------------------------------------------- #

PROCESS_MODEL = "process_model"


class _PnmlReader(InputReader):
    format_id = "pnml"
    label = "PNML (fake, test-only)"
    extensions = (".pnml",)
    kind = PROCESS_MODEL

    def read(self, stream):
        return {"raw": stream.read().decode("utf-8")}


class _PnmlHandler(InputHandler):
    kind = PROCESS_MODEL

    def __init__(self):
        self.calls: list = []

    def handle(self, data, options):
        self.calls.append(data)
        return Result(200, "Process model received", data)


class _ProcessModelPlugin(SoupPlugin):
    name = "process_model_test_plugin"
    version = "1.0.0"

    def __init__(self, handler: _PnmlHandler):
        self._handler = handler

    def register(self, ctx: PluginContext) -> None:
        ctx.add_input_reader("pnml", _PnmlReader())
        ctx.add_input_handler(PROCESS_MODEL, self._handler)


def test_extensibility_process_model_kind_invokes_its_own_handler_not_the_event_log_pipeline():
    handler = _PnmlHandler()
    db = FakeDatabase()
    storage = InMemoryFileStorage()
    import_service, repository = _build_import_service([_ProcessModelPlugin(handler)], db, storage)

    stream = io.BytesIO(b"<pnml>fake net</pnml>")
    command = ImportCommand(filename="net.pnml", stream=stream, kind=PROCESS_MODEL, options={})

    result = import_service.import_(command)

    assert result.http_status_code == 200
    assert result.message == "Process model received"
    assert len(handler.calls) == 1
    assert handler.calls[0] == {"raw": "<pnml>fake net</pnml>"}

    # the event-log pipeline never ran: no Cypher, nothing staged
    assert db.received_queries == []
    assert storage.list() == []
    assert repository.exists("net") is False
