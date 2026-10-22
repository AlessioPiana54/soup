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

import pytest

from soup.core.contracts import ConflictError, CreatedBy, NotFoundError, ObjectRef, ServiceUnavailableError, ValidationError
from soup.core.events import OBJECT_BEFORE_DELETE
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
    log = engine.import_router.import_("log_csv", upload(), "log")
    filtered = engine.operation_router.run("filter", [log.id])[0]
    filtered_twice = engine.operation_router.run("filter", [filtered.id])[0]
    model = engine.import_router.import_("pnml", upload("m.pnml"), "model")
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


def test_delete_when_the_contributor_is_gone_removes_the_entry(caplog):
    engine, core = build_test_engine()
    orphan = ObjectRef(
        id="22222222-2222-4222-8222-222222222222", name="old", kind="event_log",
        created_by=CreatedBy("importer", "uninstalled", "old_package"),
    )
    core.catalog.add(orphan)

    engine.workspace_service.delete(orphan.id)

    assert core.catalog.get(orphan.id) is None
    assert "was not disposed of" in caplog.text


def test_unknown_or_hostile_ids_and_missing_catalog():
    engine, _core, _, _, _ = _setup()

    with pytest.raises(NotFoundError):
        engine.workspace_service.get("33333333-3333-4333-8333-333333333333")
    with pytest.raises(ValidationError):
        engine.workspace_service.get("../../etc/passwd")

    bare, _ = build_test_engine(with_core_tools=False)
    with pytest.raises(ServiceUnavailableError):
        bare.workspace_service.list()
