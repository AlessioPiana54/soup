"""
------------------------------------------------------------------------
File : test_operation_router.py
Description: Tests for OperationRouter - operations offered by the kinds
             of the selected objects (one or more inputs) and by the
             available tools, fields that depend on the inputs, parameter
             validation, outputs registered with parents/created_by,
             compensation when outputs are invalid or cannot be
             registered, and 404 for an inapplicable operation.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import pytest

from soup.core.contracts import Field, NotFoundError, ObjectDraft, ValidationError
from soup.core.contracts import report
from soup.core.event_bus import EventBus
from soup.core.events import OBJECT_CREATED
from soup.core.registry import Registry
from soup.core.services.core_tools import CoreTools
from soup.core.services.operation_router import OperationRouter
from tests.fakes import InMemoryCatalog
from tests.mediator_doubles import (
    FakeImporter,
    FakeOperation,
    FakeTool,
    FeaturePackage,
    build_test_engine,
    published,
    upload,
)


def _activity_fields(inputs):
    log = inputs["log"]
    return [
        Field("activity", type="select", required=True, choices=log.meta.get("activities", ["-"])),
        Field("limit", type="number", default=10),
    ]


def _setup(*operations):
    importers = [
        FakeImporter("tab", "Table", produces="table", meta={}),
        FakeImporter("log", "Log", produces="event_log", meta={"activities": ["Create", "Ship"]}),
        FakeImporter("model", "Model", extensions=(".pnml",), produces="petri_net", meta={}),
    ]
    engine, core = build_test_engine(FeaturePackage("feature", importers=importers, operations=list(operations)))
    objects = {
        "table": engine.import_router.import_("feature.tab", upload(), "orders_table"),
        "log": engine.import_router.import_("feature.log", upload(), "orders_log"),
        "model": engine.import_router.import_("feature.model", upload("m.pnml"), "orders_model"),
    }
    return engine, core, objects


def test_operations_are_filtered_by_the_kinds_of_the_inputs():
    engine, _core, objs = _setup(
        FakeOperation("rows", inputs=[("table", ["table"])], group="Views"),
        FakeOperation("filter", inputs=[("log", ["event_log"])], produces=("event_log",)),
        FakeOperation("stats", inputs=[("any", ["table", "event_log"])], produces=("report",), group="Statistics"),
        FakeOperation("conformance", inputs=[("log", ["event_log"]), ("model", ["petri_net"])], produces=("report",)),
    )
    router = engine.operation_router

    assert [op.key for op in router.operations_for([objs["table"].id])] == ["feature.stats", "feature.rows"]
    assert [op.key for op in router.operations_for([objs["log"]])] == ["feature.filter", "feature.stats"]
    # two inputs, in either order
    assert [op.key for op in router.operations_for([objs["model"], objs["log"]])] == ["feature.conformance"]
    assert router.operations_for([objs["model"]]) == []


def test_operations_whose_tools_are_missing_are_not_offered():
    tools: Registry = Registry("tool")
    catalog = InMemoryCatalog()
    tools.register(catalog, "test", "catalog")
    tools.register(FakeTool("storage"), "test", "storage")
    operations: Registry = Registry("operation")
    for operation in (
        FakeOperation("needs_storage", inputs=[("t", ["table"])], requires_tools=("storage",)),
        FakeOperation("needs_graph", inputs=[("t", ["table"])], requires_tools=("graph",)),
    ):
        operations.register(operation, "feature", f"feature.{operation.id}")
    router = OperationRouter(operations, CoreTools(tools), EventBus())
    engine, _core, objs = _setup()
    catalog.add(objs["table"])

    assert [op.key for op in router.operations_for([objs["table"].id])] == ["feature.needs_storage"]
    with pytest.raises(NotFoundError):
        router.run("feature.needs_graph", [objs["table"].id], {})


def test_fields_depend_on_the_inputs():
    engine, _core, objs = _setup(FakeOperation("filter", inputs=[("log", ["event_log"])], fields=_activity_fields))

    fields = engine.operation_router.fields("feature.filter", [objs["log"].id])

    assert fields[0].choice_values() == ("Create", "Ship")


def test_run_registers_outputs_with_parents_and_created_by():
    operation = FakeOperation(
        "conformance",
        inputs=[("log", ["event_log"]), ("model", ["petri_net"])],
        produces=("report", "event_log"),
        result=lambda inputs, params: [
            report.report("fitness", [report.keyvalue({"fitness": 0.9})]),
            ObjectDraft("deviations", "event_log", {"cases": 3}, "Non-fitting cases"),
        ],
    )
    engine, core, objs = _setup(operation)
    created = published(engine, OBJECT_CREATED)

    outputs = engine.operation_router.run("feature.conformance", [objs["model"].id, objs["log"].id], {})

    assert operation.runs[0][0] == {"log": objs["log"].id, "model": objs["model"].id}
    assert [o.name for o in outputs] == ["fitness", "deviations"]
    for output in outputs:
        assert output.parents == (objs["log"].id, objs["model"].id)
        assert output.created_by.to_dict() == {"type": "operation", "contributor_id": "feature.conformance", "package": "feature"}
        assert core.catalog.get(output.id) == output
    assert outputs[0].meta["blocks"][0]["type"] == "keyvalue"
    assert outputs[1].description == "Non-fitting cases"
    assert [event["object"]["id"] for event in created] == [o.id for o in outputs]


def test_inputs_can_be_given_by_slot_name():
    operation = FakeOperation("conformance", inputs=[("log", ["event_log"]), ("model", ["petri_net"])])
    engine, _core, objs = _setup(operation)

    engine.operation_router.run("feature.conformance", {"model": objs["model"].id, "log": objs["log"].id})

    with pytest.raises(NotFoundError):
        engine.operation_router.run("feature.conformance", {"log": objs["model"].id, "model": objs["log"].id})


def test_run_validates_params_and_passes_cleaned_values():
    operation = FakeOperation("filter", inputs=[("log", ["event_log"])], fields=_activity_fields)
    engine, _core, objs = _setup(operation)

    engine.operation_router.run("feature.filter", [objs["log"].id], {"activity": "Ship", "limit": "5", "extra": "dropped"})
    assert operation.runs[0][1] == {"activity": "Ship", "limit": 5}

    with pytest.raises(ValidationError) as missing:
        engine.operation_router.run("feature.filter", [objs["log"].id], {})
    assert missing.value.details == {"activity": "is required"}
    assert len(operation.runs) == 1


def test_invalid_output_disposes_every_output_and_registers_none():
    operation = FakeOperation(
        "split",
        inputs=[("log", ["event_log"])],
        produces=("event_log",),
        result=lambda inputs, params: [ObjectDraft("ok", "event_log"), ObjectDraft("bad", "petri_net")],
    )
    engine, core, objs = _setup(operation)
    before = set(core.catalog.objects)

    with pytest.raises(ValueError, match="petri_net"):
        engine.operation_router.run("feature.split", [objs["log"].id])

    assert set(core.catalog.objects) == before
    assert len(operation.disposed) == 2


def test_failed_registration_removes_registered_outputs_and_disposes():
    operation = FakeOperation(
        "split",
        inputs=[("log", ["event_log"])],
        produces=("event_log",),
        result=lambda inputs, params: [ObjectDraft("first", "event_log"), ObjectDraft("second", "event_log")],
    )
    engine, core, objs = _setup(operation)
    before = set(core.catalog.objects)
    real_add = core.catalog.add

    def _add_once(obj):
        if obj.name == "second":
            raise OSError("catalog full")
        real_add(obj)

    core.catalog.add = _add_once

    with pytest.raises(OSError):
        engine.operation_router.run("feature.split", [objs["log"].id])

    assert set(core.catalog.objects) == before
    assert len(operation.disposed) == 2


def test_report_outputs_must_carry_valid_blocks():
    operation = FakeOperation(
        "stats",
        inputs=[("t", ["table"])],
        produces=("report",),
        result=lambda inputs, params: [ObjectDraft("stats", "report", {"blocks": [{"type": "html", "data": {}}]})],
    )
    engine, _core, objs = _setup(operation)

    with pytest.raises(ValueError, match="Unknown block type"):
        engine.operation_router.run("feature.stats", [objs["table"].id])
    assert len(operation.disposed) == 1


def test_missing_or_inapplicable_operation_and_missing_object_are_404():
    engine, _core, objs = _setup(FakeOperation("rows", inputs=[("t", ["table"])]))

    with pytest.raises(NotFoundError):
        engine.operation_router.run("feature.nope", [objs["table"].id])
    with pytest.raises(NotFoundError):
        engine.operation_router.run("feature.rows", [objs["log"].id])
    with pytest.raises(NotFoundError):
        engine.operation_router.run("feature.rows", [objs["table"].id, objs["log"].id])
    with pytest.raises(NotFoundError):
        engine.operation_router.run("feature.rows", ["00000000-0000-4000-8000-000000000000"])
    with pytest.raises(ValidationError):
        engine.operation_router.run("feature.rows", ["../etc"])
