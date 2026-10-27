"""
------------------------------------------------------------------------
File : test_ekg_pipeline.py
Description: Tests for the EKG build pipeline - step ordering (the ekg
             package's steps and the ones contributed to
             "ekg.build_steps", merged by `order`), the causal_df package
             taking over :DF for trigger/target entity types, that no
             query text ever embeds a raw user-supplied value, and the
             process times of each phase (ekg package's steps.py and
             ekg_service.py, soup-packages/causal_df).
Project : soup-packages/ekg
------------------------------------------------------------------------
"""

from __future__ import annotations

import pytest

from tests.fakes import FakeDatabase, ekg_engine
from tests.packages import bundled_api, bundled_module

BuildContext, ColumnMapping = bundled_api("ekg").BuildContext, bundled_api("ekg").ColumnMapping
EkgService = bundled_module("ekg", "ekg_service").EkgService
CausalDirectlyFollowsStep = bundled_api("causal_df").CausalDirectlyFollowsStep


def _plugin_build_steps(*steps) -> list:
    return list(steps)


def _ctx(entity_columns=("A", "B", "C"), trigger_target_rows=()) -> BuildContext:
    mapping = ColumnMapping(event_id="EventID", timestamp="Timestamp", activity="Activity",
                             entity_columns=entity_columns)
    return BuildContext(
        dataset_name="orders",
        mapping=mapping,
        events_csv_path="/soup/orders/orders.csv",
        entities_csv_path="/soup/orders/orders_entity.csv",
        trigger_target_rows=trigger_target_rows,
    )


def test_build_pipeline_merges_core_and_plugin_steps():
    service = EkgService(FakeDatabase(), plugin_build_steps=_plugin_build_steps(CausalDirectlyFollowsStep()))

    pipeline = service.build_pipeline()

    orders = [step.order for step in pipeline]
    assert orders == sorted(orders)
    assert [step.order for step in pipeline] == [100, 200, 300, 400, 450, 500]
    assert [step.key for step in pipeline] == [
        "load_events",
        "load_entities",
        "create_indexes",
        "correlation",
        "causal_directly_follows",
        "directly_follows",
    ]


def test_contributed_steps_are_read_at_every_build():
    contributed: list = []
    service = EkgService(FakeDatabase(), plugin_build_steps=lambda: contributed)
    assert [step.order for step in service.build_pipeline()] == [100, 200, 300, 400, 500]

    contributed.append(CausalDirectlyFollowsStep())
    assert [step.order for step in service.build_pipeline()] == [100, 200, 300, 400, 450, 500]


def test_causal_df_contributes_its_step_to_the_extension_point(tmp_path, monkeypatch):
    engine = ekg_engine(tmp_path, monkeypatch)

    steps = engine.ctx.contributions("ekg.build_steps")

    assert [(step.key, step.order) for step in steps] == [("causal_directly_follows", 450)]
    assert engine.ctx.extension_points.owner_of("ekg.build_steps") == "ekg"


def test_build_records_the_process_times_of_each_phase():
    service = EkgService(FakeDatabase(), plugin_build_steps=_plugin_build_steps(CausalDirectlyFollowsStep()))
    times: dict = {}

    service.build(_ctx(trigger_target_rows=[{"trigger": "A", "target": "B"}]), times)

    assert set(times) == {
        f"{edge}_{phase}_time" for edge in ("init", "finish") for phase in ("event", "entity", "corr", "df")
    }
    # 450 and 500 are both "df": one interval from the first start to the last end.
    assert times["init_df_time"] <= times["finish_df_time"]
    assert times["finish_corr_time"] <= times["init_df_time"]


def test_build_pipeline_without_plugin_steps_is_just_the_core_five():
    service = EkgService(FakeDatabase())
    pipeline = service.build_pipeline()
    assert [step.order for step in pipeline] == [100, 200, 300, 400, 500]


def test_causal_step_takes_over_df_for_trigger_and_target():
    db = FakeDatabase()
    service = EkgService(db, plugin_build_steps=_plugin_build_steps(CausalDirectlyFollowsStep()))
    ctx = _ctx(entity_columns=("A", "B", "C"), trigger_target_rows=[{"trigger": "A", "target": "B"}])

    service.build(ctx)

    assert ctx.df_handled_types == {"A", "B"}

    df_queries = [q for q in db.received_queries if "n.Type = $entity_type" in q.text and "MERGE (e1)-[df:DF" in q.text]
    df_handled_for = {q.params["entity_type"] for q in df_queries}
    assert df_handled_for == {"C"}  # A and B were taken over by the causal step, not the core's DirectlyFollowsStep

    # the causal step still ran its 6 parameterized queries for A/B
    causal_queries = [q for q in db.received_queries if q.params.get("trigger") == "A" and q.params.get("target") == "B"]
    assert len(causal_queries) == 5  # 4 trigger+target-parameterized + 1 target-only (find/set x2 + target_df)
    trigger_only = [q for q in db.received_queries if q.params == {"trigger": "A"}]
    assert len(trigger_only) == 1


def test_causal_step_does_not_apply_without_trigger_target_rows():
    db = FakeDatabase()
    service = EkgService(db, plugin_build_steps=_plugin_build_steps(CausalDirectlyFollowsStep()))
    ctx = _ctx(entity_columns=("A", "B"), trigger_target_rows=[])

    service.build(ctx)

    assert ctx.df_handled_types == set()
    causal_queries = [q for q in db.received_queries if "relation = 'causal'" in q.text or "relation: 'causal'" in q.text]
    assert causal_queries == []


def test_no_query_text_ever_embeds_a_raw_user_supplied_value():
    hostile_value = "A'; DETACH DELETE n; //"

    db = FakeDatabase()
    service = EkgService(db, plugin_build_steps=_plugin_build_steps(CausalDirectlyFollowsStep()))
    ctx = _ctx(entity_columns=("A",), trigger_target_rows=[{"trigger": hostile_value, "target": "A"}])

    service.build(ctx)

    assert len(db.received_queries) > 0
    for query in db.received_queries:
        assert hostile_value not in query.text
    # it only ever travels as a bound parameter
    assert any(query.params.get("trigger") == hostile_value for query in db.received_queries)


def test_hostile_entity_column_name_is_rejected_outright_not_embedded():
    # Column/identifier names cannot be parameterized in Cypher at all, so
    # the guard for them is ident() rejecting anything that is not a
    # simple identifier - the hostile text never reaches a query.
    db = FakeDatabase()
    service = EkgService(db)
    ctx = _ctx(entity_columns=("A; DROP",))

    with pytest.raises(ValueError):
        service.build(ctx)

    assert db.received_queries == [] or all("DROP" not in q.text for q in db.received_queries)
