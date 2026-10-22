"""
------------------------------------------------------------------------
File : test_import_router.py
Description: Tests for ImportRouter - every importer accepting a file is
             offered, inspect/preview reach the chosen one, the import
             creates a typed object (kind, created_by, uuid id) and
             publishes "object.created", a failed import is compensated
             with dispose(), and bad names are refused.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest

from soup.core.contracts import NotFoundError, ServiceUnavailableError, ValidationError
from soup.core.event_bus import EventBus
from soup.core.events import OBJECT_CREATED
from soup.core.registry import Registry
from soup.core.services.core_tools import CoreTools
from soup.core.services.import_router import ImportRouter
from tests.fakes import InMemoryCatalog
from tests.mediator_doubles import FakeImporter, FeaturePackage, build_test_engine, published, upload


def _importers():
    as_table = FakeImporter("csv_table", "Table (CSV)", produces="table")
    as_log = FakeImporter("csv_log", "Event log (CSV)", produces="event_log")
    as_text = FakeImporter("txt", "Plain text", extensions=(".txt",), produces="text")
    return as_table, as_log, as_text


def test_two_importers_on_the_same_extension_are_both_offered():
    as_table, as_log, as_text = _importers()
    engine, _core = build_test_engine(FeaturePackage("feature", importers=[as_table, as_log, as_text]))

    assert [i.id for i in engine.import_router.importers_for("LOG.CSV")] == ["csv_log", "csv_table"]
    assert [i.id for i in engine.import_router.importers_for("notes.txt")] == ["txt"]
    assert engine.import_router.importers_for("image.png") == []


def test_inspect_and_preview_are_routed_to_the_chosen_importer():
    as_table, as_log, _ = _importers()
    engine, _core = build_test_engine(FeaturePackage("feature", importers=[as_table, as_log]))
    file = upload()

    inspection = engine.import_router.inspect("csv_log", file)
    blocks = engine.import_router.preview("csv_log", file, {"separator": ";"})

    assert inspection.preview[0]["data"]["text"] == "csv_log:a,b\n1,2\n"
    assert [field.name for field in inspection.fields] == ["separator"]
    assert blocks == [{"type": "text", "title": "", "data": {"text": "csv_log separator=;"}}]
    assert as_log.calls == [("inspect", "log.csv"), ("preview", {"separator": ";"})]
    assert as_table.calls == []


def test_unknown_importer_is_404_and_an_importer_refusing_the_file_is_400():
    as_table, _, as_text = _importers()
    engine, _core = build_test_engine(FeaturePackage("feature", importers=[as_table, as_text]))

    with pytest.raises(NotFoundError):
        engine.import_router.inspect("missing", upload())
    with pytest.raises(ValidationError):
        engine.import_router.inspect("txt", upload("log.csv"))


def test_import_creates_a_typed_object_and_publishes_object_created():
    as_table, as_log, _ = _importers()
    as_log.meta = {"events": 10}
    engine, core = build_test_engine(FeaturePackage("feature", importers=[as_table, as_log]))
    created = published(engine, OBJECT_CREATED)

    obj = engine.import_router.import_("csv_log", upload(), "orders", "My orders", {"separator": ","})

    uuid.UUID(obj.id)
    assert (obj.name, obj.kind, obj.parents, obj.description) == ("orders", "event_log", (), "My orders")
    assert obj.created_by.to_dict() == {"type": "importer", "contributor_id": "csv_log", "package": "feature"}
    assert obj.meta == {"events": 10}
    assert core.catalog.get(obj.id) == obj
    assert created == [{"object": obj.to_dict()}]
    # the importer received the object before its meta was attached
    assert as_log.calls[-1][1].id == obj.id and as_log.calls[-1][1].meta == {}


def test_names_need_not_be_unique_ids_are():
    engine, core = build_test_engine(FeaturePackage("feature", importers=[FakeImporter("csv_table", "Table")]))

    first = engine.import_router.import_("csv_table", upload(), "orders")
    second = engine.import_router.import_("csv_table", upload(), "orders")

    assert first.id != second.id
    assert len(core.catalog.list()) == 2


def test_created_at_uses_the_process_timer_format():
    importer = FakeImporter("csv_table", "Table")
    importers: Registry = Registry("importer")
    importers.register(importer, "feature", importer.id)
    tools: Registry = Registry("tool")
    tools.register(InMemoryCatalog(), "test", "catalog")
    router = ImportRouter(importers, CoreTools(tools), EventBus(), clock=lambda: datetime(2025, 1, 2, 3, 4, 5, 678901))

    assert router.import_("csv_table", upload(), "ds").created_at == "2025-01-02T03:04:05.678"


def test_failed_import_is_compensated_with_dispose_and_re_raised():
    failing = FakeImporter("csv_table", "Table", fail_with=RuntimeError("disk full"))
    engine, core = build_test_engine(FeaturePackage("feature", importers=[failing]))
    created = published(engine, OBJECT_CREATED)

    with pytest.raises(RuntimeError, match="disk full"):
        engine.import_router.import_("csv_table", upload(), "orders")

    attempted = failing.calls[-1][1]
    assert failing.disposed == [attempted.id]
    assert core.catalog.list() == []
    assert created == []


def test_failed_registration_is_compensated_too():
    importer = FakeImporter("csv_table", "Table")
    engine, core = build_test_engine(FeaturePackage("feature", importers=[importer]))

    def _refuse(obj):
        raise OSError("catalog full")

    core.catalog.add = _refuse

    with pytest.raises(OSError, match="catalog full"):
        engine.import_router.import_("csv_table", upload(), "orders")
    assert len(importer.disposed) == 1


def test_invalid_meta_is_compensated():
    bad_meta = FakeImporter("csv_table", "Table", meta=["not", "a", "dict"])
    engine, core = build_test_engine(FeaturePackage("feature", importers=[bad_meta]))

    with pytest.raises(TypeError):
        engine.import_router.import_("csv_table", upload(), "orders")
    assert len(bad_meta.disposed) == 1
    assert core.catalog.list() == []


def test_compensation_failure_does_not_hide_the_original_error(caplog):
    failing = FakeImporter("csv_table", "Table", fail_with=RuntimeError("original"))

    def _broken_dispose(obj, tools):
        raise OSError("cleanup failed too")

    failing.dispose = _broken_dispose
    engine, _core = build_test_engine(FeaturePackage("feature", importers=[failing]))

    with pytest.raises(RuntimeError, match="original"):
        engine.import_router.import_("csv_table", upload(), "orders")
    assert "Compensation failed" in caplog.text


@pytest.mark.parametrize(
    "name", ["", ".", "..", "a/b", "a\\b", "../etc", "a..b", "_hidden", " padded", "padded ", "new\nline", "x" * 129]
)
def test_hostile_names_are_refused_before_the_importer_runs(name):
    importer = FakeImporter("csv_table", "Table")
    engine, core = build_test_engine(FeaturePackage("feature", importers=[importer]))

    with pytest.raises(ValidationError) as invalid:
        engine.import_router.import_("csv_table", upload(), name)

    assert invalid.value.http_status_code == 400
    assert importer.calls == []
    assert core.catalog.list() == []


def test_import_without_a_catalog_tool_is_503():
    importer = FakeImporter("csv_table", "Table")
    engine, _core = build_test_engine(FeaturePackage("feature", importers=[importer]), with_core_tools=False)

    with pytest.raises(ServiceUnavailableError) as unavailable:
        engine.import_router.import_("csv_table", upload(), "orders")

    assert unavailable.value.http_status_code == 503
    assert "'catalog' tool" in str(unavailable.value)
    assert importer.calls == []
    assert [i.id for i in engine.import_router.importers_for("x.csv")] == ["csv_table"]
