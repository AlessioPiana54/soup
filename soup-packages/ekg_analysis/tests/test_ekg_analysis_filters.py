"""
------------------------------------------------------------------------
File : test_ekg_analysis_filters.py
Description: The filters of ekg_analysis without a graph: every value of
             the user travels as a parameter and never in the text of the
             query, the operators come only from the closed list ("!="
             becomes "<>"), each filter validates its conditions like the
             legacy validate*Filter (the error names the filter, the
             position and the field), clean_timestamp drops only the time
             zone, the order of the filters does not depend on the order
             of the items, and the legacy configuration format round-trips.
Project : soup-packages/ekg_analysis
------------------------------------------------------------------------
"""

from __future__ import annotations

import pytest

from soup.core.contracts import ServiceUnavailableError, ValidationError
from tests.fakes import FakeDatabase
from tests.packages import bundled_module

filters = bundled_module("ekg_analysis", "filters")
analysis_module = bundled_module("ekg_analysis", "analysis")
Analysis = analysis_module.Analysis

# Values that would break (or inject into) a query put in its text.
EVIL = "x'}) DETACH DELETE n //"
CONDITIONS = {
    "timestamp": {"startDate": "2021-05-01T22:00:00.000Z", "endDate": "2021-05-09T21:00:00+02:00"},
    "performance": {"entity": EVIL, "operator": ">=", "seconds": 4242},
    "includeActivities": {"activities": [EVIL]},
    "excludeActivities": {"activities": [EVIL, "Ship"]},
    "frequence": {"entity": EVIL, "operator": "<", "frequency": 4343},
    "variant": {"entity": EVIL, "operator": "=", "variant": 4444},
}


def _by_key():
    return {item.key: item for item in filters.builtin_filters()}


def _context(activities=("Create", "Ship", EVIL)):
    db = FakeDatabase()
    db.set_response(filters.activities_query().text, [{"activity": name} for name in activities])
    return filters.FilterContext(db.run)


def test_the_six_filters_keep_the_legacy_order():
    assert [item.key for item in filters.builtin_filters()] == [
        "timestamp", "performance", "includeActivities", "excludeActivities", "frequence", "variant"]
    assert [item.order for item in filters.builtin_filters()] == [100, 200, 300, 400, 500, 600]
    assert filters.LEGACY_FILTER_KEYS == tuple(CONDITIONS)


def test_filter_values_travel_as_parameters():
    ctx = _context()
    for key, item in _by_key().items():
        condition = item.validate(CONDITIONS[key])
        queries = item.to_queries(condition, ctx)
        assert queries, key
        for query in queries:
            for value in (EVIL, "4242", "4343", "4444", "2021-05-01", "2021-05-09"):
                assert value not in query.text, (key, value)
        params = [query.params for query in queries]
        if key == "timestamp":
            assert params == [{"start": "2021-05-01T22:00:00.000", "end": "2021-05-09T21:00:00"}]
        elif key == "performance":
            assert params == [{"entity": EVIL, "duration": "PT4242S"}]
        elif key == "includeActivities":
            # The activities not chosen are excluded, one query each.
            assert params == [{"activity": "Create"}, {"activity": "Ship"}]
        elif key == "excludeActivities":
            assert params == [{"activity": EVIL}, {"activity": "Ship"}]
        elif key == "frequence":
            assert params == [{"entity": EVIL, "frequency": 4343}]
        else:
            assert params == [{"entity": EVIL, "variant": 4444}]


def test_labels_and_types_are_quoted_in_the_pattern():
    [query] = _by_key()["variant"].to_queries({"entity": "Order", "operator": "=", "variant": 1}, _context())
    assert "MATCH (e:`Event`)-[:`CORR`]->(t:`Entity` {Type: $entity})" in query.text
    [query] = _by_key()["timestamp"].to_queries(CONDITIONS["timestamp"], _context())
    assert "MATCH (e1:`Event`)-[r:`DF`]->(e2:`Event`)" in query.text


@pytest.mark.parametrize("key, field", [("performance", "seconds"), ("frequence", "frequency"), ("variant", "variant")])
def test_operators_are_whitelisted(key, field):
    item = _by_key()[key]
    for operator, cypher in filters.OPERATORS.items():
        [query] = item.to_queries(item.validate({"entity": "Order", "operator": operator, field: 2}), _context())
        assert f" {cypher} " in query.text
    [query] = item.to_queries(item.validate({"entity": "Order", "operator": "!=", field: 2}), _context())
    assert " <> " in query.text and "!=" not in query.text

    for operator in ("<>", "==", "> 0 OR 1 =", "", None, "LIKE"):
        with pytest.raises(ValidationError, match="operator"):
            item.validate({"entity": "Order", "operator": operator, field: 2})


@pytest.mark.parametrize("key, condition, field", [
    ("timestamp", {"endDate": "2021-01-01T00:00:00"}, "startDate"),
    ("timestamp", {"startDate": "yesterday", "endDate": "2021-01-01T00:00:00"}, "startDate"),
    ("timestamp", {"startDate": "2021-01-01T00:00:00", "endDate": 7}, "endDate"),
    ("performance", {"operator": ">", "seconds": 10}, "entity"),
    ("performance", {"entity": "Order", "operator": ">", "seconds": 0}, "seconds"),
    ("performance", {"entity": "Order", "operator": ">", "seconds": "many"}, "seconds"),
    ("performance", {"entity": "Order", "operator": ">", "seconds": True}, "seconds"),
    ("includeActivities", {"activities": []}, "activities"),
    ("excludeActivities", {"activities": "Ship"}, "activities"),
    ("excludeActivities", {"activities": ["Ship", 3]}, "activities"),
    ("frequence", {"entity": "Order", "operator": ">", "frequency": -1}, "frequency"),
    ("frequence", {"entity": "Order", "operator": ">", "frequency": 1.5}, "frequency"),
    ("variant", {"entity": " ", "operator": ">", "variant": 1}, "entity"),
    ("variant", {"entity": "Order", "operator": ">"}, "variant"),
])
def test_each_filter_validates_its_conditions(key, condition, field):
    with pytest.raises(ValidationError, match=field):
        _by_key()[key].validate(condition)


def test_valid_conditions_are_normalized():
    by_key = _by_key()
    assert by_key["performance"].validate({"entity": "Order", "operator": ">", "seconds": "2.5"})["seconds"] == 2.5
    assert by_key["frequence"].validate({"entity": "Order", "operator": ">", "frequency": "3"})["frequency"] == 3
    assert by_key["excludeActivities"].validate({"activities": ["A", "A", "B"]}) == {"activities": ["A", "B"]}
    with pytest.raises(ValidationError):
        by_key["timestamp"].validate(["not", "an", "object"])


@pytest.mark.parametrize("raw, cleaned", [
    ("2024-01-01T10:00:00+01:00", "2024-01-01T10:00:00"),
    ("2024-01-01T10:00:00-05:00", "2024-01-01T10:00:00"),
    ("2024-01-01T10:00:00-0500", "2024-01-01T10:00:00"),
    ("2021-05-01T22:00:00.000Z", "2021-05-01T22:00:00.000"),
    ("2021-05-01T22:00:00", "2021-05-01T22:00:00"),
    ("2021-05-01", "2021-05-01"),
])
def test_clean_timestamp_drops_only_the_time_zone(raw, cleaned):
    # The legacy clean_timestamp turned "2024-01-01T10:00:00+01:00" into "2024".
    assert filters.clean_timestamp(raw) == cleaned


def test_the_order_of_the_filters_does_not_depend_on_the_order_of_the_items():
    items = [
        {"variant": "variant", "values": CONDITIONS["variant"]},
        {"variant": "excludeActivities", "values": {"activities": ["Ship"]}},
        {"variant": "timestamp", "values": CONDITIONS["timestamp"]},
        {"variant": "excludeActivities", "values": {"activities": ["Pack"]}},
    ]
    analysis = Analysis.from_items("a1", items, filters.builtin_filters())

    ordered = analysis.ordered(filters.builtin_filters())
    assert [(item.key, condition.get("activities")) for item, condition in ordered] == [
        ("timestamp", None), ("excludeActivities", ["Ship"]), ("excludeActivities", ["Pack"]), ("variant", None)]


def test_items_are_validated_one_by_one():
    items = [
        {"variant": "performance", "values": {"entity": "Order", "operator": "~", "seconds": 1}},
        {"variant": "nope", "values": {}},
        {"variant": "excludeActivities", "values": {"activities": ["Ship"]}},
    ]
    with pytest.raises(ValidationError) as error:
        Analysis.from_items("a1", items, filters.builtin_filters())
    message = str(error.value)
    assert "filters[0] (performance): operator" in message and "filters[1]: unknown filter 'nope'" in message


def test_the_legacy_format_round_trips_and_is_validated_filter_by_filter():
    content = {key: [condition] for key, condition in CONDITIONS.items()}
    content.update({"dataset_name": "orders", "analysis_name": "old", "analysis_description": "Una vecchia analisi"})

    analysis = Analysis.from_legacy("old", content, filters.builtin_filters())
    assert analysis.description == "Una vecchia analisi"
    assert analysis.to_legacy("orders") == {**{key: [_by_key()[key].validate(c)] for key, c in CONDITIONS.items()},
                                            "dataset_name": "orders", "analysis_name": "old",
                                            "analysis_description": "Una vecchia analisi"}
    # The six legacy keys are always written, also when empty.
    assert set(Analysis("a1", {}).to_legacy("orders")) >= set(filters.LEGACY_FILTER_KEYS)

    broken = {"performance": [{"entity": "Order", "operator": ">", "seconds": 1}, {"entity": "Order", "operator": ">"}],
              "frequence": {"entity": "Order"}, "magic": [{}]}
    with pytest.raises(ValidationError) as error:
        Analysis.from_legacy("old", broken, filters.builtin_filters())
    message = str(error.value)
    assert "performance[1]: seconds" in message and "frequence: must be a list" in message and "magic: unknown filter" in message
    with pytest.raises(ValidationError):
        Analysis.from_legacy("old", ["not", "an", "object"], filters.builtin_filters())


def test_a_filter_no_active_package_contributes_is_a_503():
    analysis = Analysis("a1", {"magic": [{}]})
    with pytest.raises(ServiceUnavailableError, match="magic"):
        analysis.ordered(filters.builtin_filters())


@pytest.mark.parametrize("name", ["", "..", "a/b", "_hidden"])
def test_analysis_names_are_validated(name):
    with pytest.raises(ValidationError):
        Analysis(name, {})
