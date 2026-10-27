"""
------------------------------------------------------------------------
File : test_ekg_analysis_insights.py
Description: The "Indicatori di processo" visualizer of ekg_analysis on a
             FakeDatabase: data() with the entity types, the frequency of
             the activities and the indicators of the first type; the
             action "entity" (average duration of the traces, occurrences
             of the activities, variants with their average duration) with
             the entity type as a parameter and checked against the
             graph's types; the action "frequency" with its threshold; the
             conversion of the Memgraph durations.
Project : soup-packages/ekg_analysis
------------------------------------------------------------------------
"""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

import pytest

from soup.core.contracts import NotFoundError, Upload, ValidationError
from tests.fakes import EKG_PACKAGES, FakeDatabase, ekg_engine
from tests.packages import bundled_module

filters = bundled_module("ekg_analysis", "filters")
insights = bundled_module("ekg_analysis", "insights")

CSV = b"case,activity,time,order\n1,Create,2021-01-01T10:00:00.000,o1\n2,Ship,2021-01-01T11:00:00.000,o1\n"
OPTIONS = {"event_id": "case", "timestamp": "time", "activity": "activity", "entities": ["order"]}
VISUALIZER = "ekg_analysis.insights"


def _duration(seconds: int):
    """A Memgraph Duration as the driver gives it."""

    return SimpleNamespace(months=0, days=seconds // 86400, seconds=seconds % 86400, nanoseconds=0)


@pytest.fixture
def setup(tmp_path, monkeypatch):
    db = FakeDatabase()
    db.set_response(filters.entity_types_query().text, [{"entity_type": "order"}, {"entity_type": "item"}])
    db.set_response(insights.activity_frequency_query(1).text, [{"activity": "Ship", "frequency": 1}, {"activity": "Create", "frequency": 2}])
    db.set_response(insights.trace_durations_query("order").text, [
        {"entity_id": "o1", "iso_duration": _duration(3600)}, {"entity_id": "o2", "iso_duration": _duration(7200)},
        {"entity_id": "o3", "iso_duration": None}])
    db.set_response(insights.activity_occurrences_query("order").text, [{"activity": "Create", "occurrences": 2}])
    db.set_response(insights.variants_query("order").text, [
        {"variant": ["Create", "Ship"], "occurrences": 2, "durations": [_duration(60), _duration(120)]},
        {"variant": ["Create"], "occurrences": 1, "durations": []}])
    engine = ekg_engine(tmp_path, monkeypatch, packages=(*EKG_PACKAGES, "ekg_analysis"), db=db)
    root = engine.import_router.import_("csv_ekg.csv", Upload.from_bytes("orders.csv", CSV), "orders", options=OPTIONS)
    return engine, db, root


def test_data_has_the_types_the_frequency_and_the_indicators_of_the_first_type(setup):
    engine, _db, root = setup

    data = engine.visualizer_router.data(VISUALIZER, root.id, {})

    assert data["entity_types"] == ["order", "item"]
    assert data["frequency"] == [{"activity": "Ship", "frequency": 1}, {"activity": "Create", "frequency": 2}]
    assert data["indicators"]["entity"] == "order"
    assert data["indicators"]["duration"]["formatted"] == "1:30:00"
    assert data["notice"] is None


def test_the_indicators_of_an_entity_type(setup):
    engine, db, root = setup

    result = engine.visualizer_router.action(VISUALIZER, root.id, "entity", {"entity": "order"})

    assert result["duration"] == {"average_seconds": 5400.0, "formatted": "1:30:00", "count": 2}
    assert result["activities"] == [{"activity": "Create", "occurrences": 2}]
    assert result["variants"] == [
        {"variant": ["Create", "Ship"], "occurrences": 2, "average_seconds": 90.0, "formatted": "0:01:30"},
        {"variant": ["Create"], "occurrences": 1, "average_seconds": None, "formatted": None},
    ]
    entity_queries = [query for query in db.received_queries if query.params.get("entity") == "order"]
    assert len(entity_queries) == 3
    assert all("order" not in query.text for query in entity_queries)


def test_an_entity_type_not_in_the_graph_is_a_400(setup):
    engine, db, root = setup
    start = len(db.received_queries)

    with pytest.raises(ValidationError, match="entity"):
        engine.visualizer_router.action(VISUALIZER, root.id, "entity", {"entity": "x'}) DETACH DELETE n //"})
    assert not any("entity" in query.params for query in db.received_queries[start:])


def test_the_frequency_has_a_threshold(setup):
    engine, db, root = setup

    result = engine.visualizer_router.action(VISUALIZER, root.id, "frequency", {"min": "3"})

    assert result["min"] == 3
    assert db.received_queries[-1].params == {"min": 3}
    for wrong in ("0", "many", -2):
        with pytest.raises(ValidationError, match="min"):
            engine.visualizer_router.action(VISUALIZER, root.id, "frequency", {"min": wrong})
    with pytest.raises(NotFoundError):
        engine.visualizer_router.action(VISUALIZER, root.id, "explode", {})


def test_durations_are_read_like_the_legacy_code():
    assert insights.duration_seconds(SimpleNamespace(months=1, days=1, seconds=10, nanoseconds=500_000_000)) == (
        30 * 86400 + 86400 + 10.5)
    assert insights.duration_seconds(timedelta(minutes=2)) == 120
    assert insights.duration_seconds(7) == 7.0
    assert insights.duration_seconds(None) is None
    assert insights.duration_seconds("PT1S") is None
    assert insights.average([]) is None
