"""
------------------------------------------------------------------------
File : test_ekg_extensibility.py
Description: Proves the event log is extensible WITHOUT touching soup/core
             or the ekg package: every package here is defined inside
             this test file and wired up only through public contracts
             (SoupPlugin, PluginContext, Importer) and the ekg package's
             api.py (EventLogData, Table.from_records, ColumnMapping,
             build_ekg, dispose) - exactly what a real package in
             soup-packages/ would use (moved from soup-server/tests; the
             InputReader/InputHandler pair of the old core is now an
             importer).

             - a flat JSON Lines importer, built with Table.from_records;
             - an OCEL 2.0-style importer producing separated
               events/objects/event_objects tables, and the entities/
               correlations EventLog.from_data is expected to derive
               from them;
             - an importer of an entirely new kind ("process_model"):
               it runs, and the EKG pipeline never does.
Project : soup-packages/ekg
------------------------------------------------------------------------
"""

from __future__ import annotations

import csv
import io
import json

from soup.core.contracts import Importer, Inspection, PluginContext, SoupPlugin, Upload
from tests.fakes import FakeDatabase, ekg_engine, volume_files
from tests.packages import bundled_api

ekg = bundled_api("ekg")


def _read_csv_rows(text: str) -> list[list[str]]:
    reader = csv.reader(io.StringIO(text))
    return list(reader)


def _volume(tmp_path, path: str) -> str:
    return (tmp_path / "volume" / path).read_text(encoding="utf-8")


class _EkgImporter(Importer):
    """An importer of a test package: read() turns the file into an EventLogData."""

    produces = ekg.EKG_KIND
    requires_tools = ("memgraph", "storage")
    standard_columns = ("EventID", "Timestamp", "Activity")
    entity_columns: tuple = ()

    def read(self, data: bytes):
        raise NotImplementedError

    def inspect(self, upload: Upload, tools) -> Inspection:
        return Inspection()

    def import_(self, upload, obj, options, tools):
        mapping = ekg.ColumnMapping(*self.standard_columns, entity_columns=self.entity_columns)
        return ekg.build_ekg(obj, self.read(upload.read()), mapping, tools, source_format=self.id)

    def dispose(self, obj, tools) -> None:
        ekg.dispose(obj, tools)


class _Package(SoupPlugin):
    version = "1.0.0"
    requires = ("ekg",)
    requires_tools = ("memgraph", "storage")

    def __init__(self, name: str, importer: Importer):
        self.name = name
        self._importer = importer

    def register(self, ctx: PluginContext) -> None:
        ctx.add_importer(self._importer)


# ---------------------------------------------------------------------- #
# 1. Flat JSON Lines importer, built with Table.from_records
# ---------------------------------------------------------------------- #

class _JsonLinesImporter(_EkgImporter):
    id = "jsonl"
    label = "JSON Lines"
    extensions = (".jsonl",)
    entity_columns = ("Items",)

    def read(self, data: bytes):
        records = [json.loads(line) for line in data.decode("utf-8").splitlines() if line.strip()]
        return ekg.EventLogData(events=ekg.Table.from_records(records))


def test_extensibility_jsonl_flat_importer_built_with_table_from_records(tmp_path, monkeypatch):
    engine = ekg_engine(tmp_path, monkeypatch, extra_plugins=[_Package("jsonl_test", _JsonLinesImporter())])

    jsonl_content = "\n".join([
        json.dumps({"EventID": "e1", "Activity": "Create", "Timestamp": "2021-01-01T10:00:00.000", "Items": "i1,i2"}),
        json.dumps({"EventID": "e2", "Activity": "Ship", "Timestamp": "2021-01-01T11:00:00.000", "Items": "i1"}),
    ])
    obj = engine.import_router.import_(
        "jsonl_test.jsonl", Upload.from_bytes("log.jsonl", jsonl_content.encode("utf-8")), "jsonl_ds"
    )

    assert (obj.kind, obj.meta["dataset"], obj.meta["source_format"]) == ("ekg", "jsonl_ds", "jsonl")
    rows = _read_csv_rows(_volume(tmp_path, "jsonl_ds/jsonl_ds.csv"))
    assert rows[0] == ["event_id", "timestamp", "activity_name", "Items"]
    assert ["e1", "2021-01-01T10:00:00.000", "Create", "i1,i2"] in rows


# ---------------------------------------------------------------------- #
# 2. OCEL 2.0-style importer (separated events/objects/event_objects)
# ---------------------------------------------------------------------- #

class _OcelLikeImporter(_EkgImporter):
    id = "ocel"
    label = "OCEL 2.0-like"
    extensions = (".ocel.json",)

    def accepts(self, filename: str) -> bool:
        return filename.lower().endswith(".ocel.json")

    def read(self, data: bytes):
        payload = json.loads(data.decode("utf-8"))
        return ekg.EventLogData(
            events=ekg.Table.from_records(payload["events"]),
            objects=ekg.Table.from_records(payload["objects"]),
            event_objects=ekg.Table.from_records(payload["event_objects"]),
        )


def test_extensibility_ocel_style_separated_importer_produces_expected_entities_and_correlations(tmp_path, monkeypatch):
    db = FakeDatabase()
    engine = ekg_engine(tmp_path, monkeypatch, db=db, extra_plugins=[_Package("ocel_test", _OcelLikeImporter())])

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
    engine.import_router.import_(
        "ocel_test.ocel", Upload.from_bytes("log.ocel.json", json.dumps(payload).encode("utf-8")), "ocel_ds"
    )

    # entities: both order objects, even though o2 only ever appears via
    # event_objects (never as an events-table column, since this is the
    # separated form)
    entity_rows = _read_csv_rows(_volume(tmp_path, "ocel_ds/ocel_ds_entity.csv"))
    assert entity_rows[0] == ["value", "type"]
    assert ["o1", "order"] in entity_rows
    assert ["o2", "order"] in entity_rows

    # correlation: the synthesized "order" column comma-joins e1's two
    # linked objects, in event_objects order
    event_rows = _read_csv_rows(_volume(tmp_path, "ocel_ds/ocel_ds.csv"))
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
# 3. A brand-new kind ("process_model"): its importer runs, the EKG
#    pipeline never does.
# ---------------------------------------------------------------------- #

PROCESS_MODEL = "process_model"


class _PnmlImporter(Importer):
    id = "pnml"
    label = "PNML (fake, test-only)"
    extensions = (".pnml",)
    produces = PROCESS_MODEL

    def __init__(self):
        self.calls: list = []

    def inspect(self, upload, tools) -> Inspection:
        return Inspection()

    def import_(self, upload, obj, options, tools):
        self.calls.append(upload.read().decode("utf-8"))
        return {"raw": self.calls[-1]}

    def dispose(self, obj, tools) -> None:
        pass


class _ProcessModelPackage(SoupPlugin):
    name = "process_model_test"
    version = "1.0.0"

    def __init__(self, importer: _PnmlImporter):
        self._importer = importer

    def register(self, ctx: PluginContext) -> None:
        ctx.add_importer(self._importer)


def test_extensibility_process_model_kind_runs_its_own_importer_not_the_ekg_pipeline(tmp_path, monkeypatch):
    importer = _PnmlImporter()
    db = FakeDatabase()
    engine = ekg_engine(tmp_path, monkeypatch, db=db, extra_plugins=[_ProcessModelPackage(importer)])

    obj = engine.import_router.import_("process_model_test.pnml", Upload.from_bytes("net.pnml", b"<pnml>fake net</pnml>"), "net")

    assert (obj.kind, obj.meta) == (PROCESS_MODEL, {"raw": "<pnml>fake net</pnml>"})
    assert importer.calls == ["<pnml>fake net</pnml>"]

    # the EKG pipeline never ran: no Cypher, nothing staged
    assert db.received_queries == []
    assert volume_files(tmp_path) == []
