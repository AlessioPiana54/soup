"""
------------------------------------------------------------------------
File : test_ekg_state.py
Description: The graph state of "ekg" objects (ekg package, state.py and
             builder.py) on the real memgraph tool over a FakeDatabase:
             an import leaves its object as the active state;
             ensure_loaded does not rebuild an active state, rebuilds
             with force or for another object, and for a derived object
             applies the state of a test provider (contributed to
             "ekg.state_providers") after rebuilding the root;
             "ekg.before_reset" is published before every emptying or
             rebuild, "ekg.built" after a build; dispose empties the
             graph of an active object and removes its files; the "load"
             operation.
Project : soup-packages/ekg
------------------------------------------------------------------------
"""

from __future__ import annotations

from typing import Any, Mapping

import pytest

from soup.core.contracts import (
    GraphDatabase,
    NotFoundError,
    ObjectDraft,
    Operation,
    OperationInput,
    PluginContext,
    ServiceUnavailableError,
    SoupPlugin,
    Upload,
)
from tests.fakes import FakeDatabase, ekg_engine, volume_files
from tests.packages import bundled_api

ekg = bundled_api("ekg")

CSV = b"case,activity,time,order,item\n1,Create,2021-01-01T10:00:00.000,o1,i1\n2,Ship,2021-01-01T11:00:00.000,o1,i2\n"
OPTIONS = {"event_id": "case", "timestamp": "time", "activity": "activity", "entities": ["order", "item"]}

CLEAR = "MATCH (n) DETACH DELETE n"


class _FilterProvider(ekg.StateProvider):
    key = "test.only_activity"

    def apply(self, spec: Mapping[str, Any], db: GraphDatabase) -> None:
        db.run(ekg.Query("MATCH (e:Event) WHERE e.ActivityName <> $activity DETACH DELETE e", {"activity": spec["activity"]}))


class _Derive(Operation):
    """ekg -> a derived ekg object keeping only one activity (meta.state)."""

    id = "derive"
    label = "Only one activity"
    inputs = (OperationInput("ekg", (ekg.EKG_KIND,)),)
    produces = (ekg.EKG_KIND,)
    requires_tools = ("memgraph", "storage")

    def run(self, inputs, params, tools):
        state = {"provider": _FilterProvider.key, "spec": {"activity": "Create"}}
        return [ObjectDraft(f"{inputs['ekg'].name} - Create", ekg.EKG_KIND, {"state": state})]

    def dispose(self, obj, tools) -> None:
        ekg.dispose(obj, tools)


class _StatePackage(SoupPlugin):
    name = "state_test"
    version = "1.0.0"
    requires = ("ekg",)
    requires_tools = ("memgraph", "storage")

    def __init__(self, provide: bool = True):
        self.provide = provide
        self.events: list[tuple[str, dict, int]] = []
        self.db: FakeDatabase | None = None

    def register(self, ctx: PluginContext) -> None:
        if self.provide:
            ctx.contribute(ekg.STATE_PROVIDERS_POINT, _FilterProvider(), key=_FilterProvider.key)
        ctx.add_operation(_Derive())
        for event in (ekg.EKG_BEFORE_RESET, ekg.EKG_BUILT):
            ctx.subscribe(event, lambda payload, event=event: self.events.append(
                (event, dict(payload), len(self.db.received_queries) if self.db else 0)
            ))


@pytest.fixture
def setup(tmp_path, monkeypatch):
    db = FakeDatabase()
    package = _StatePackage()
    package.db = db
    engine = ekg_engine(tmp_path, monkeypatch, db=db, extra_plugins=[package])
    assert engine.report.failed == [], engine.report.failed
    return engine, db, package


def _import(engine, name="orders"):
    return engine.import_router.import_("csv_ekg.csv", Upload.from_bytes("orders.csv", CSV), name, options=OPTIONS)


def _tools(engine):
    return engine.core_tools.toolbox("test", ("memgraph", "storage"))


def _memgraph(engine):
    return engine.ctx.tool_registry.get("memgraph")


def _texts(db: FakeDatabase, start: int = 0) -> list[str]:
    return [query.text for query in db.received_queries[start:]]


def test_an_import_leaves_its_object_as_the_active_state(setup):
    engine, db, package = setup
    obj = _import(engine)

    assert _memgraph(engine).current_state() == obj.meta["graph_key"]
    events = [(event, payload.get("object")) for event, payload, _ in package.events]
    assert events == [(ekg.EKG_BEFORE_RESET, obj.id), (ekg.EKG_BUILT, obj.id)]
    built = package.events[-1][1]
    assert (built["dataset"], set(built["counts"])) == ("orders", {"event_nodes", "entity_nodes", "corr_rel", "df_rel"})


def test_ensure_loaded_does_not_rebuild_an_active_state(setup):
    engine, db, package = setup
    obj = _import(engine)
    before, published = len(db.received_queries), len(package.events)

    assert ekg.ensure_loaded(obj, _tools(engine)) is False

    assert len(db.received_queries) == before
    assert len(package.events) == published


def test_ensure_loaded_rebuilds_with_force_or_for_another_object(setup):
    engine, db, _package = setup
    first, second = _import(engine, "first"), _import(engine, "second")
    assert _memgraph(engine).current_state() == second.meta["graph_key"]

    start = len(db.received_queries)
    assert ekg.ensure_loaded(first, _tools(engine)) is True
    texts = _texts(db, start)
    assert texts[0] == CLEAR
    assert any("/first/first.csv" in text for text in texts if text.startswith("LOAD CSV"))
    assert _memgraph(engine).current_state() == first.meta["graph_key"]

    start = len(db.received_queries)
    assert ekg.ensure_loaded(first, _tools(engine), force=True) is True
    assert _texts(db, start)[0] == CLEAR


def test_before_reset_is_published_before_every_rebuild(setup):
    engine, db, package = setup
    first, second = _import(engine, "first"), _import(engine, "second")
    ekg.ensure_loaded(first, _tools(engine))
    ekg.ensure_loaded(first, _tools(engine), force=True)

    clears = [index for index, query in enumerate(db.received_queries) if query.text == CLEAR]
    resets = [(payload, seen) for event, payload, seen in package.events if event == ekg.EKG_BEFORE_RESET]
    # Two imports and two loads: four emptyings, each announced before it happened.
    assert len(clears) == len(resets) == 4
    assert all(seen <= clear for (_, seen), clear in zip(resets, clears))
    assert [payload["reason"] for payload, _ in resets] == ["build", "build", "load", "load"]
    assert resets[2][0]["active"] == second.meta["graph_key"]


def test_a_derived_object_is_loaded_by_its_provider_after_rebuilding_the_root(setup):
    engine, db, _package = setup
    root = _import(engine)
    [derived] = engine.operation_router.run("state_test.derive", [root.id])
    assert derived.parents == (root.id,)

    start = len(db.received_queries)
    assert ekg.ensure_loaded(derived, _tools(engine)) is True

    texts = _texts(db, start)
    load = next(index for index, text in enumerate(texts) if text.startswith("LOAD CSV"))
    applied = next(index for index, query in enumerate(db.received_queries[start:]) if query.params.get("activity") == "Create")
    assert load < applied
    assert _memgraph(engine).current_state() == derived.id
    # Already active: nothing to do; the root is another state.
    assert ekg.ensure_loaded(derived, _tools(engine)) is False
    assert ekg.ensure_loaded(root, _tools(engine)) is True


def test_a_derived_object_without_its_provider_answers_503(tmp_path, monkeypatch):
    package = _StatePackage(provide=False)
    engine = ekg_engine(tmp_path, monkeypatch, extra_plugins=[package])
    root = _import(engine)
    [derived] = engine.operation_router.run("state_test.derive", [root.id])

    with pytest.raises(ServiceUnavailableError, match="test.only_activity"):
        ekg.ensure_loaded(derived, _tools(engine))


def test_a_derived_object_needs_an_ekg_parent(setup):
    engine, _db, _package = setup
    root = _import(engine)
    [derived] = engine.operation_router.run("state_test.derive", [root.id])
    engine.core_tools.catalog().remove(root.id)

    with pytest.raises(NotFoundError):
        ekg.ensure_loaded(derived, _tools(engine))


def test_deleting_the_active_object_empties_the_graph_and_removes_its_files(setup, tmp_path):
    engine, db, package = setup
    first, second = _import(engine, "first"), _import(engine, "second")

    engine.workspace_service.delete(first.id)  # not active: files only
    assert [path for path in volume_files(tmp_path) if path.startswith("first/")] == []
    assert _memgraph(engine).current_state() == second.meta["graph_key"]

    start = len(db.received_queries)
    engine.workspace_service.delete(second.id)
    assert _texts(db, start) == [CLEAR]
    assert _memgraph(engine).current_state() is None
    assert volume_files(tmp_path) == []
    assert package.events[-1][0] == ekg.EKG_BEFORE_RESET
    assert package.events[-1][1]["reason"] == "dispose"


def test_the_load_operation_runs_ensure_loaded(setup):
    engine, db, _package = setup
    first, _second = _import(engine, "first"), _import(engine, "second")
    assert {entry.key for entry in engine.operation_router.operations_for([first.id])} == {"ekg.load", "state_test.derive"}

    assert engine.operation_router.run("ekg.load", [first.id]) == []
    assert _memgraph(engine).current_state() == first.meta["graph_key"]

    start = len(db.received_queries)
    engine.operation_router.run("ekg.load", [first.id])
    assert _texts(db, start) == []
    engine.operation_router.run("ekg.load", [first.id], {"force": True})
    assert _texts(db, start)[0] == CLEAR


def test_a_rebuild_saves_the_counts_and_times_in_the_config(setup, tmp_path):
    engine, db, _package = setup
    obj = _import(engine)
    db.set_response("MATCH (n:Event) RETURN COUNT(n) AS count", [{"count": 7}])

    ekg.ensure_loaded(obj, _tools(engine), force=True)

    import json

    config = json.loads((tmp_path / "volume" / "orders" / "orders_config.json").read_text(encoding="utf-8"))
    assert config["event_nodes"] == 7
    assert config["process_info"]["init_df_time"] is not None
    assert config["date_created"] == obj.meta["date_created"]
