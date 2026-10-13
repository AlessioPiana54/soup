"""
------------------------------------------------------------------------
File : test_ekg_schema.py
Description: Tests for soup.core.ekg.schema - the explicit index list,
             and that EkgService.reset() drops exactly (and only) the
             indexes the build actually creates (correction of the
             legacy drop_event_index() dropping :Event(Event_Id), an
             index Services/generic_graph_service.py's build never
             creates - see Utils/general_query_lib.py, not modified by
             this session).
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from soup.core.ekg import schema
from soup.core.services.ekg_service import EkgService
from tests.fakes import FakeDatabase


def test_created_indexes_are_exactly_entity_value_and_event_activity():
    created = [factory().text for factory in schema.CREATED_INDEXES]
    assert created == ["CREATE INDEX ON :Entity(Value)", "CREATE INDEX ON :Event(ActivityName)"]


def test_dropped_indexes_match_created_indexes_one_to_one():
    created_targets = {text.split("ON ")[1] for text in (factory().text for factory in schema.CREATED_INDEXES)}
    dropped_targets = {text.split("ON ")[1] for text in (factory().text for factory in schema.DROPPED_INDEXES)}
    assert created_targets == dropped_targets


def test_dropped_indexes_never_reference_event_event_id():
    # The legacy bug this corrects: Utils/general_query_lib.py's
    # drop_event_index() drops :Event(Event_Id), an index never created.
    for factory in schema.DROPPED_INDEXES:
        assert "Event_Id" not in factory().text


def test_reset_runs_delete_and_drop_queries_for_exactly_the_created_indexes():
    db = FakeDatabase()
    service = EkgService(db)

    service.reset()

    index_drop_queries = [q.text for q in db.received_queries if q.text.startswith("DROP INDEX")]
    assert index_drop_queries == ["DROP INDEX ON :Entity(Value)", "DROP INDEX ON :Event(ActivityName)"]

    delete_queries = [q.text for q in db.received_queries if "DETACH DELETE" in q.text]
    assert any("Event" in q for q in delete_queries)
    assert any("Entity" in q for q in delete_queries)


def test_rebuild_resets_then_builds():
    from soup.core.contracts import BuildContext
    from soup.core.event_log import ColumnMapping

    db = FakeDatabase()
    service = EkgService(db)
    ctx = BuildContext(
        dataset_name="orders",
        mapping=ColumnMapping(event_id="EventID", timestamp="Timestamp", activity="Activity"),
        events_csv_path="/soup/orders/orders.csv",
        entities_csv_path="/soup/orders/orders_entity.csv",
    )

    service.rebuild(ctx)

    texts = [q.text for q in db.received_queries]
    reset_index = next(i for i, t in enumerate(texts) if t.startswith("DROP INDEX"))
    build_index = next(i for i, t in enumerate(texts) if t.startswith("LOAD CSV"))
    assert reset_index < build_index  # reset happens before the rebuild's load
