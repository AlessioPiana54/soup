"""
------------------------------------------------------------------------
File : test_ekg_views_queries.py
Description: The GraphQuery contributions of ekg_views (builtin_queries.py)
             and the JSON parts (json_parts.py), on canned rows: every
             query produces the expected blocks; labels and relationship
             types are in the pattern (MATCH (n:`Event`), [r:`DF`]),
             quoted by ident() from the query's own closed list; the LIMIT
             and every user value travel as parameters, never in the
             Cypher text; the
             LIMIT is an integer clamped to the maximum; the counts are
             always read from the column "count" (the legacy code read
             ['count'] from queries aliased node_count/entity_count); the
             JSON parts have the format of the /api/v2/json/graph/*
             endpoints; Memgraph date-times and NaN are made JSON-ready.
Project : soup-packages/ekg_views
------------------------------------------------------------------------
"""

from __future__ import annotations

import math
from datetime import datetime

import pytest

from soup.core.contracts import ValidationError, report
from tests.packages import bundled_module

builtin = bundled_module("ekg_views", "builtin_queries")
queries = bundled_module("ekg_views", "queries")
parts = bundled_module("ekg_views", "json_parts")
values = bundled_module("ekg_views", "values")

QUERIES = {query.key: query for query in builtin.builtin_queries()}

EVENT = {"Event_Id": "1", "Timestamp": datetime(2021, 1, 1, 10, 0, 0), "ActivityName": "Create", "order": "o1", "cost": math.nan}
ENTITY = {"Value": "o1", "Type": "order"}


class _MemgraphDateTime:
    """Like neo4j.time.DateTime: year...second and nanosecond attributes."""

    year, month, day, hour, minute, second, nanosecond = 2021, 1, 2, 3, 4, 5, 6_000


def _run(key, rows, params=None):
    query = QUERIES[key]
    checked = query.values(params or {})
    built = query.build(checked)
    blocks = query.transform(rows, checked)
    return built, report.validate_blocks(blocks)


def test_about_twenty_queries_cover_every_legacy_read():
    assert len(QUERIES) == 20
    assert {query.group for query in QUERIES.values()} == {"Nodi", "Relazioni", "Conteggi", "Attività", "Entità", "Tempo", "Grafo"}
    assert all(query.label for query in QUERIES.values())


@pytest.mark.parametrize("key", ["event_nodes", "entity_nodes"])
def test_node_lists_are_paged_tables_with_the_total(key):
    rows = [{"total": 7, "id": 4, "props": EVENT if key == "event_nodes" else ENTITY}]
    built, [block] = _run(key, rows, {"limit": "25", "offset": 50})

    assert block["type"] == "table"
    assert block["data"]["total"] == 7
    assert built.params["limit"] == 25 and built.params["offset"] == 50
    if key == "event_nodes":
        assert block["data"]["columns"] == ["id", "Event_Id", "Timestamp", "ActivityName", "cost", "order"]
        assert block["data"]["rows"] == [[4, "1", "2021-01-01T10:00:00.000000", "Create", None, "o1"]]
    else:
        assert block["data"]["columns"] == ["id", "Value", "Type"]


def test_filters_are_parameters_never_text():
    hostile = "Pay' OR 1=1 //"
    built, _ = _run("events_of_activity", [], {"activity": hostile, "limit": 3})
    assert built.params["activity"] == hostile and hostile not in built.text
    built, _ = _run("entities_of_type", [], {"type": hostile})
    assert built.params["type"] == hostile and hostile not in built.text
    built, _ = _run("df_of_type", [], {"entity_type": hostile})
    assert built.params["entity_type"] == hostile and hostile not in built.text


def test_a_required_filter_is_checked():
    with pytest.raises(ValidationError, match="activity"):
        QUERIES["events_of_activity"].values({})


@pytest.mark.parametrize("key", [key for key, query in QUERIES.items() if any(spec.name == "limit" for spec in query.fields)])
def test_the_limit_is_a_parameter_and_not_in_the_text(key):
    query = QUERIES[key]
    params = {"limit": 987, "activity": "a", "type": "t", "entity_type": "t"}
    built = query.build(query.values(params))
    assert "$limit" in built.text
    assert "987" not in built.text
    assert built.params["limit"] == 987


def test_the_limit_is_an_integer_clamped_to_the_maximum():
    query = QUERIES["event_nodes"]
    assert query.values({"limit": 10**9})["limit"] == queries.MAX_ROWS
    assert query.values({"limit": 0})["limit"] == 1
    assert query.values({})["limit"] == queries.DEFAULT_ROWS
    for bad in ("ten", True, 2.5, "1; DROP"):
        with pytest.raises(ValidationError, match="limit"):
            query.values({"limit": bad})


def test_relationship_lists_name_their_endpoints():
    rows = [{"total": 1, "id": 9, "source": EVENT, "type": "CORR", "props": {"Type": "order"}, "target": ENTITY}]
    built, [block] = _run("corr", rows)

    assert "MATCH (a:`Event`)-[r:`CORR`]->(b:`Entity`)" in built.text
    assert built.params == {"offset": 0, "limit": 100}
    assert block["data"]["columns"] == ["id", "sorgente", "tipo", "destinazione", "Type"]
    assert block["data"]["rows"] == [[9, "Create", "CORR", "o1", "order"]]
    assert "MATCH (a:`Event`)-[r:`DF`]->(b:`Event`)" in _run("df", [])[0].text


@pytest.mark.parametrize("key, label, pattern", [
    ("count_events", "Nodi evento", "MATCH (n:`Event`)"),
    ("count_entities", "Nodi entità", "MATCH (n:`Entity`)"),
    ("count_corr", "Relazioni CORR", "MATCH ()-[r:`CORR`]->()"),
    ("count_df", "Relazioni DF", "MATCH ()-[r:`DF`]->()"),
    ("count_nodes", "Tutti i nodi", "MATCH (n)"),
])
def test_counts_read_the_count_column(key, label, pattern):
    built, [block] = _run(key, [{"count": 12}])
    assert pattern in built.text and "AS count" in built.text and built.params == {}
    assert block == {"type": "keyvalue", "title": label, "data": {"items": [{"key": label, "value": 12}]}}
    # An alias other than "count" is not a count (no silent fallback to another column).
    assert _run(key, [{"node_count": 12}])[1][0]["data"]["items"][0]["value"] == 0
    assert _run(key, [])[1][0]["data"]["items"][0]["value"] == 0


def test_activities_and_their_frequency():
    _, [block] = _run("activities", [{"activities": ["Ship", "Create"]}])
    assert block["data"]["rows"] == [["Create"], ["Ship"]]
    assert block["title"] == "Attività distinte (2)"

    _, [chart, table] = _run("activity_frequency", [{"activity": "Create", "count": 3}, {"activity": "Ship", "count": 1}])
    assert chart["data"] == {"chart": "bar", "labels": ["Create", "Ship"], "datasets": [{"label": "eventi", "data": [3, 1]}]}
    assert table["data"]["rows"] == [["Create", 3], ["Ship", 1]]


def test_entities():
    _, [block] = _run("entity_keys", [{"entity_type": "item"}, {"entity_type": "order"}])
    assert block["data"]["rows"] == [["item"], ["order"]]

    _, [chart, _table] = _run("entities_per_type", [{"entity_type": "order", "count": 2}])
    assert chart["data"]["chart"] == "pie" and chart["data"]["labels"] == ["order"]

    _, [block] = _run("null_entities", [{"prop": "order", "count": 4}])
    assert block["data"]["rows"] == [["order", 4]]

    _, [block] = _run("entity_per_type", [{"type": "order", "props": ENTITY}])
    assert block["data"]["rows"] == [["order", "o1"]]


def test_timestamps_are_iso_strings():
    _, [block] = _run("timestamps", [{"min_timestamp": 20210101100000, "max_timestamp": 20211231235959}])
    assert block["data"]["items"] == [{"key": "primo", "value": "2021-01-01T10:00:00"}, {"key": "ultimo", "value": "2021-12-31T23:59:59"}]
    _, [block] = _run("timestamps", [])
    assert block["data"]["items"][0]["value"] is None


def test_max_data_counts_nodes_and_relationships_without_apoc():
    built, [block] = _run("max_data", [{"total_nodes": 5, "total_rels": 4}])
    assert "apoc" not in built.text
    assert "MATCH (a:`Event`)-[r:`DF`]->(b:`Event`)" in built.text
    assert "ORDER BY" not in built.text
    assert block["data"]["items"][-1] == {"key": "totale", "value": 9}


def test_every_query_describes_its_fields():
    described = QUERIES["events_of_activity"].describe()
    assert described["key"] == "events_of_activity"
    assert [field["name"] for field in described["fields"]] == ["activity", "limit", "offset"]


def test_clean_converts_memgraph_values():
    assert values.clean({"t": _MemgraphDateTime(), "n": math.nan, "l": [math.nan, 1]}) == {
        "t": "2021-01-02T03:04:05.000006", "n": None, "l": [None, 1],
    }


def test_json_parts_have_the_v2_format():
    by_key = {part.key: part for part in parts.builtin_parts()}
    assert [part.label for part in by_key.values()] == ["Event nodes", "Entity nodes", "CORR relationships", "DF relationships"]

    assert by_key["event_nodes"].transform([{"node": EVENT}]) == [
        {"Event_Id": "1", "Timestamp": "2021-01-01T10:00:00.000000", "ActivityName": "Create", "order": "o1", "cost": None}
    ]
    corr = by_key["corr"].transform([{"event": EVENT, "relation_type": "CORR", "related_event": ENTITY}] * 2)
    assert corr["corr_count"] == 2
    assert corr["corr_data"][1] == {"event": corr["corr_data"][0]["event"], "relation_type": "CORR", "related_event": ENTITY, "relation_id": 2}
    df = by_key["df"].transform([])
    assert df == {"df_data": [], "df_count": 0}
    assert "MATCH (a:`Event`)-[r:`DF`]->(b:`Event`)" in by_key["df"].query().text
    assert "MATCH (n:`Entity`)" in by_key["entity_nodes"].query().text
    assert "MATCH (a:`Event`)-[r:`CORR`]->(b:`Entity`)" in by_key["corr"].query().text
    assert all(part.query().params == {} for part in by_key.values())


# The labelled pattern every generated query must contain.
PATTERNS = {
    "event_nodes": "MATCH (n:`Event`)",
    "entity_nodes": "MATCH (n:`Entity`)",
    "entity_per_type": "MATCH (e:Entity)",
    "entities_of_type": "MATCH (n:`Entity`) WHERE n.Type = $type",
    "events_of_activity": "MATCH (n:`Event`) WHERE n.ActivityName = $activity",
    "corr": "MATCH (a:`Event`)-[r:`CORR`]->(b:`Entity`)",
    "df": "MATCH (a:`Event`)-[r:`DF`]->(b:`Event`)",
    "df_of_type": "MATCH (a:`Event`)-[r:`DF`]->(b:`Event`) WHERE r.Type = $entity_type",
    "count_events": "MATCH (n:`Event`)",
    "count_entities": "MATCH (n:`Entity`)",
    "count_corr": "MATCH ()-[r:`CORR`]->()",
    "count_df": "MATCH ()-[r:`DF`]->()",
    "count_nodes": "MATCH (n)",
    "activities": "MATCH (n:Event)",
    "activity_frequency": "MATCH (e:Event)",
    "entity_keys": "MATCH (n:Entity)",
    "entities_per_type": "MATCH (n:Entity)",
    "null_entities": "MATCH (e:Event)",
    "timestamps": "MATCH (n:Event)",
    "max_data": "MATCH (a:`Event`)-[r:`DF`]->(b:`Event`)",
}

HOSTILE = "x`) DETACH DELETE n //"


@pytest.mark.parametrize("key", sorted(QUERIES))
def test_every_query_has_its_labelled_pattern_and_no_user_value(key):
    query = QUERIES[key]
    raw = {spec.name: HOSTILE for spec in query.fields if spec.type == "text"}
    raw.update({"limit": 77, "offset": 31})
    built = query.build(query.values(raw))

    assert PATTERNS[key] in built.text
    # No generic filter of labels or types after an unlabelled MATCH.
    assert "labels(" not in built.text and "type(r) =" not in built.text and "IN $" not in built.text
    assert HOSTILE not in built.text and "77" not in built.text and "31" not in built.text
    for name, value in raw.items():
        if name in built.params:
            assert built.params[name] == value


def test_a_label_or_type_that_needs_quoting_goes_through_ident():
    count = queries.CountQuery("odd", "Odd", node_label="MATCH")
    assert "MATCH (n:`MATCH`)" in count.build({}).text
    listed = queries.RelationshipListQuery("odd_rel", "Odd", source_label="Order", relationship="DELETE", target_label="Order")
    assert "MATCH (a:`Order`)-[r:`DELETE`]->(b:`Order`)" in listed.build(listed.values({})).text
    # A name ident() cannot quote safely never reaches the text.
    for bad in ("Event`) DETACH DELETE n //", "has space", "1st"):
        with pytest.raises(ValueError):
            queries.CountQuery("bad", "Bad", node_label=bad).build({})
        with pytest.raises(ValueError):
            parts.NodesPart("bad", "Bad", bad).query()
