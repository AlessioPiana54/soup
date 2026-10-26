"""
------------------------------------------------------------------------
File : test_workspace_service.py
Description: Tests for WorkspaceService - provenance tree, rename and
             description, thumbnails, delete with and without cascade,
             "object.before_delete", and dispose() called on the
             contributor that created each object.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from soup.core.contracts import ConflictError, CreatedBy, NotFoundError, ObjectRef, ServiceUnavailableError, ValidationError
from soup.core.events import OBJECT_BEFORE_DELETE
from soup.core.services.orphaned_data import OrphanedDataLog
from soup.core.services.workspace_service import WorkspaceService
from tests.mediator_doubles import FakeImporter, FakeOperation, FeaturePackage, build_test_engine, published, upload


def _setup():
    importer = FakeImporter("log_csv", "Log", produces="event_log")
    model_importer = FakeImporter("pnml", "Model", extensions=(".pnml",), produces="petri_net")
    filter_op = FakeOperation("filter", inputs=[("log", ["event_log"])], produces=("event_log",))
    conformance = FakeOperation("conformance", inputs=[("log", ["event_log"]), ("model", ["petri_net"])], produces=("report",),
                                result=lambda inputs, params: [])
    engine, core = build_test_engine(
        FeaturePackage("logs", importers=[importer], operations=[filter_op]),
        FeaturePackage("models", importers=[model_importer], operations=[conformance], requires=("logs",)),
    )
    log = engine.import_router.import_("logs.log_csv", upload(), "log")
    filtered = engine.operation_router.run("logs.filter", [log.id])[0]
    filtered_twice = engine.operation_router.run("logs.filter", [filtered.id])[0]
    model = engine.import_router.import_("models.pnml", upload("m.pnml"), "model")
    return engine, core, importer, filter_op, {"log": log, "filtered": filtered, "twice": filtered_twice, "model": model}


def _names(nodes):
    return [(node.object.name, _names(node.children)) for node in nodes]


def test_list_is_a_provenance_tree():
    engine, _core, _, _, objs = _setup()

    tree = engine.workspace_service.list()

    assert _names(tree) == [
        ("log", [("filter of log", [("filter of filter of log", [])])]),
        ("model", []),
    ]
    assert tree[0].to_dict()["children"][0]["object"]["id"] == objs["filtered"].id


def test_object_with_two_parents_appears_under_both():
    engine, core, _, _, objs = _setup()
    core.catalog.add(ObjectRef(
        id="11111111-1111-4111-8111-111111111111", name="fitness", kind="report",
        created_by=CreatedBy("operation", "conformance", "models"),
        parents=(objs["log"].id, objs["model"].id), created_at="9999",
    ))

    tree = {node.object.name: node for node in engine.workspace_service.list()}

    assert "fitness" in [child.object.name for child in tree["log"].children]
    assert [child.object.name for child in tree["model"].children] == ["fitness"]


def test_rename_description_and_thumbnail():
    engine, core, _, _, objs = _setup()
    log_id = objs["log"].id

    assert engine.workspace_service.rename(log_id, "orders").name == "orders"
    assert engine.workspace_service.update_description(log_id, "2025 orders").description == "2025 orders"
    assert core.catalog.get(log_id).name == "orders"
    with pytest.raises(ValidationError):
        engine.workspace_service.rename(log_id, "../x")

    assert engine.workspace_service.get_thumbnail(log_id) is None
    engine.workspace_service.set_thumbnail(log_id, "<svg/>")
    assert engine.workspace_service.get_thumbnail(log_id) == "<svg/>"


def test_delete_without_cascade_of_an_object_with_children_is_409():
    engine, core, importer, filter_op, objs = _setup()

    with pytest.raises(ConflictError) as conflict:
        engine.workspace_service.delete(objs["log"].id)

    assert conflict.value.http_status_code == 409
    assert conflict.value.details == {"children": [objs["filtered"].id]}
    assert importer.disposed == [] and filter_op.disposed == []
    assert core.catalog.get(objs["log"].id) is not None


def test_delete_with_cascade_removes_children_first_and_disposes_through_the_right_contributor():
    engine, core, importer, filter_op, objs = _setup()
    before_delete = published(engine, OBJECT_BEFORE_DELETE)

    deleted = engine.workspace_service.delete(objs["log"].id, cascade=True)

    expected = [objs["twice"].id, objs["filtered"].id, objs["log"].id]
    assert deleted == expected
    assert [event["object"]["id"] for event in before_delete] == expected
    assert filter_op.disposed == [objs["twice"].id, objs["filtered"].id]
    assert importer.disposed == [objs["log"].id]
    assert [obj.name for obj in core.catalog.list()] == ["model"]


def test_delete_of_a_leaf_needs_no_cascade():
    engine, core, _, filter_op, objs = _setup()

    assert engine.workspace_service.delete(objs["twice"].id) == [objs["twice"].id]
    assert filter_op.disposed == [objs["twice"].id]


def test_critical_before_delete_subscriber_can_veto():
    engine, core, importer, _, objs = _setup()

    def _veto(payload):
        raise ConflictError("in use by an open view")

    engine.event_bus.subscribe(OBJECT_BEFORE_DELETE, _veto, owner="viewer", critical=True)

    with pytest.raises(ConflictError, match="in use"):
        engine.workspace_service.delete(objs["model"].id)
    assert core.catalog.get(objs["model"].id) is not None


def _orphan(object_id="22222222-2222-4222-8222-222222222222", parents=()):
    return ObjectRef(
        id=object_id, name="old", kind="event_log", parents=parents,
        created_by=CreatedBy("importer", "old_package.uninstalled", "old_package"), meta={"graph": "old"},
    )


def test_delete_when_the_contributor_is_gone_is_409_naming_the_package():
    engine, core = build_test_engine()
    core.catalog.add(_orphan())

    with pytest.raises(ConflictError, match="'old_package' is not active") as error:
        engine.workspace_service.delete(_orphan().id)

    assert error.value.details == {"packages": ["old_package"], "objects": [_orphan().id]}
    assert "force=true" in str(error.value)
    assert core.catalog.get(_orphan().id) is not None


def test_cascade_is_409_when_a_descendant_belongs_to_an_inactive_package():
    engine, core, importer, filter_op, objs = _setup()
    child = _orphan("44444444-4444-4444-8444-444444444444", parents=(objs["log"].id,))
    core.catalog.add(child)

    with pytest.raises(ConflictError) as error:
        engine.workspace_service.delete(objs["log"].id, cascade=True)

    assert error.value.details["objects"] == [child.id]
    # Nothing was deleted or disposed of.
    assert importer.disposed == [] and filter_op.disposed == []
    assert core.catalog.get(objs["log"].id) is not None


def test_force_removes_from_the_catalog_and_records_the_orphaned_data(tmp_path, caplog):
    engine, core = build_test_engine()
    log = OrphanedDataLog(tmp_path / "orphaned-data.json", clock=lambda: datetime(2025, 1, 2, 3, 4, 5))
    service = WorkspaceService(engine.ctx.importers, engine.ctx.operations, engine.core_tools, engine.event_bus,
                               orphaned_data=log)
    core.catalog.add(_orphan())

    assert service.delete(_orphan().id, force=True) == [_orphan().id]

    assert core.catalog.get(_orphan().id) is None
    assert "was not disposed of" in caplog.text
    [entry] = json.loads((tmp_path / "orphaned-data.json").read_text(encoding="utf-8"))
    assert entry["package"] == "old_package"
    assert entry["object"]["meta"] == {"graph": "old"}
    assert entry["contributor"]["contributor_id"] == "old_package.uninstalled"
    assert entry["removed_at"] == "2025-01-02T03:04:05.000"


def test_engine_records_orphaned_data_in_the_installed_packages_folder(tmp_path):
    from soup.core.engine import build_engine
    from soup.core.settings import Settings
    from tests.fakes import CoreToolsPackage

    tools = CoreToolsPackage()
    settings = Settings(packages_path=(), installed_packages_dir=str(tmp_path))
    engine = build_engine(settings, extra_plugins=[tools])
    tools.catalog.add(_orphan())

    engine.workspace_service.delete(_orphan().id, force=True)

    entries = json.loads((tmp_path / "orphaned-data.json").read_text(encoding="utf-8"))
    assert [entry["object"]["id"] for entry in entries] == [_orphan().id]


def test_unknown_or_hostile_ids_and_missing_catalog():
    engine, _core, _, _, _ = _setup()

    with pytest.raises(NotFoundError):
        engine.workspace_service.get("33333333-3333-4333-8333-333333333333")
    with pytest.raises(ValidationError):
        engine.workspace_service.get("../../etc/passwd")

    bare, _ = build_test_engine(with_core_tools=False)
    with pytest.raises(ServiceUnavailableError):
        bare.workspace_service.list()
