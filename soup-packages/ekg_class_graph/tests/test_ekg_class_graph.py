"""
------------------------------------------------------------------------
File : test_ekg_class_graph.py
Description: The aggregate graph on the real host with the bundled
             packages, a FakeDatabase and the local storage on tmp_path:
             "Costruisci grafo aggregato" creates an "ekg_class" object
             derived from its "ekg" input (meta.state, meta.graph_key,
             counts, times), with quoted identifiers and the entity types
             checked against the graph; ekg's ensure_loaded rebuilds the
             parent and applies the classes once; a failed build creates
             nothing and rebuilds the parent. The Observer: with the
             package active the queries of an analysis include the
             deletion of the Class nodes that no line of ekg_analysis asks
             for (and a deletion that leaves Class nodes cancels the
             analysis); disabled, the analysis works and "ekg_class" has no
             operation, visualizer or exporter. The kinds: on an "ekg"
             object only the standard queries and JSON parts, on an
             "ekg_class" object the standard ones and the classes', each
             part under its own key; the two visualizers.
Project : soup-packages/ekg_class_graph
------------------------------------------------------------------------
"""

from __future__ import annotations

import json

import pytest

from soup.core.contracts import DomainError, NotFoundError, Upload, ValidationError
from tests.fakes import ANALYSIS_PACKAGES, FakeDatabase, ekg_engine
from tests.packages import bundled_module

classes = bundled_module("ekg_class_graph", "classes")

CSV = b"case,activity,time,order,item\n1,Create,2021-01-01T10:00:00.000,o1,i1\n2,Ship,2021-01-01T11:00:00.000,o1,i2\n"
OPTIONS = {"event_id": "case", "timestamp": "time", "activity": "activity", "entities": ["order", "item"]}
DELETE_CLASSES = "MATCH (n:`Class`) DETACH DELETE n"
COUNT_CLASSES = "MATCH (n:`Class`) RETURN count(n) AS count"
COUNT_NODES = "MATCH (n) RETURN count(n) AS count"
EXCLUDE_SHIP = {"variant": "excludeActivities", "values": {"activities": ["Ship"]}}


class ClassDatabase(FakeDatabase):
    """A FakeDatabase with the entity types of CSV that fails on the queries containing `fail_on`."""

    def __init__(self) -> None:
        super().__init__()
        self.fail_on: str | None = None
        self.set_response(classes.entity_types_query().text, [{"entity_type": "item"}, {"entity_type": "order"}])

    def run(self, query):
        if self.fail_on and self.fail_on in query.text:
            self.received_queries.append(query)
            raise RuntimeError("Memgraph failed")
        return super().run(query)

    def texts(self, start: int = 0) -> list[str]:
        return [query.text for query in self.received_queries[start:]]


def _engine(tmp_path, monkeypatch, packages=ANALYSIS_PACKAGES):
    db = ClassDatabase()
    engine = ekg_engine(tmp_path, monkeypatch, packages=packages, db=db)
    assert engine.report.failed == [], engine.report.failed
    root = engine.import_router.import_("csv_ekg.csv", Upload.from_bytes("orders.csv", CSV), "orders", options=OPTIONS)
    return engine, db, root


@pytest.fixture
def setup(tmp_path, monkeypatch):
    return _engine(tmp_path, monkeypatch)


def _build(engine, root, types=("order", "item"), name="aggregato"):
    [obj] = engine.operation_router.run("ekg_class_graph.build", [root.id], {"name": name, "entity_types": list(types)})
    return obj


def _state(engine):
    return engine.ctx.tool_registry.get("memgraph").current_state()


def _rebuilt(db, start) -> bool:
    return any(text.startswith("LOAD CSV") for text in db.texts(start))


def test_building_the_aggregate_graph_creates_a_derived_ekg_class_object(setup):
    engine, db, root = setup
    db.set_response(COUNT_CLASSES, [{"count": 3}])
    db.set_response(classes.nan_properties_query().text, [{"prop": "Odd_name", "node_count": 1},
                                                          {"prop": "x` = 1 DETACH DELETE n //", "node_count": 1}])
    start = len(db.received_queries)

    obj = _build(engine, root)

    assert (obj.kind, obj.parents, obj.name) == ("ekg_class", (root.id,), "aggregato")
    assert obj.meta["state"] == {"provider": "ekg_class_graph.classes", "spec": {"entity_types": ["order", "item"]}}
    assert obj.meta["entity_types"] == ["order", "item"]
    assert obj.meta["counts"] == {"class_nodes": 3, "obs_rel": 0, "dfc_rel": 0}
    assert set(obj.meta["process_info"]) == {
        "init_class_time", "finish_class_time", "init_class_node_time", "finish_class_node_time",
        "init_obs_time", "finish_obs_time", "init_dfc_time", "finish_dfc_time"}
    assert _state(engine) == obj.meta["graph_key"] != root.meta["graph_key"]
    # Built on the loaded parent: no rebuild.
    assert not _rebuilt(db, start)

    texts = db.texts(start)
    assert "MATCH (n:`Event`) SET n.`Odd_name` = toString(n.`Odd_name`)" in texts
    assert not any("DETACH DELETE n //" in text for text in texts)
    [query] = [item for item in db.received_queries[start:] if "MERGE (c:`Class`" in item.text]
    assert "WITH DISTINCT e.`order` AS v0, e.`item` AS v1" in query.text
    assert '`order`: v0, `item`: v1, Event_Id: "c_" + toString(v0) + "_" + toString(v1), Type: $class_type' in query.text
    assert query.params == {"class_type": "Class"}
    [dfc] = [text for text in texts if "MERGE (c1)-[:`DF_C`" in text]
    assert "-[r:`DF`]->" in dfc and "type(r)" not in dfc


def test_entity_types_are_checked_against_the_graph(setup):
    engine, db, root = setup
    [_name, entity_types] = engine.operation_router.fields("ekg_class_graph.build", [root.id])
    assert entity_types.choice_values() == ("item", "order")

    with pytest.raises(ValidationError, match="entity_types"):
        _build(engine, root, types=("order", "x`) DETACH DELETE n //"))
    assert not any("MERGE (c:`Class`" in text for text in db.texts())


def test_entity_types_with_null_values_carry_the_warning(setup):
    engine, db, root = setup
    nulls = bundled_module("ekg_views", "builtin_queries").NullEntities()
    db.set_response(nulls.build({}).text, [{"prop": "order", "count": 2}])

    [_name, entity_types] = engine.operation_router.fields("ekg_class_graph.build", [root.id])

    assert [(choice.value, choice.label) for choice in entity_types.choices] == [
        ("item", "item"), ("order", "order (2 nodi hanno valore NaN.)"),
    ]


def test_ensure_loaded_rebuilds_the_parent_and_applies_the_classes_once(setup):
    engine, db, root = setup
    obj = _build(engine, root)
    engine.visualizer_router.data("ekg_views.stats", root.id, {})
    assert _state(engine) == root.meta["graph_key"]

    start = len(db.received_queries)
    engine.visualizer_router.data("ekg_class_graph.stats", obj.id, {})
    texts = db.texts(start)
    load = next(index for index, text in enumerate(texts) if text.startswith("LOAD CSV"))
    built = [index for index, text in enumerate(texts) if "MERGE (c:`Class`" in text]
    assert len(built) == 1 and load < built[0]
    assert _state(engine) == obj.meta["graph_key"]

    start = len(db.received_queries)
    engine.visualizer_router.data("ekg_class_graph.graph", obj.id, {})
    engine.visualizer_router.data("ekg_class_graph.stats", obj.id, {})
    assert not _rebuilt(db, start)
    assert not any("MERGE (c:`Class`" in text for text in db.texts(start))


def test_a_failed_build_creates_nothing_and_rebuilds_the_parent(setup):
    engine, db, root = setup
    db.fail_on = "MERGE (c1)-[:`DF_C`"
    before = [item.id for item in engine.core_tools.catalog().list()]
    start = len(db.received_queries)

    with pytest.raises(RuntimeError, match="Memgraph failed"):
        _build(engine, root)

    assert [item.id for item in engine.core_tools.catalog().list()] == before
    assert _rebuilt(db, start)
    assert _state(engine) == root.meta["graph_key"]


def test_an_analysis_deletes_the_class_nodes_that_no_line_of_ekg_analysis_asks_for(setup):
    engine, db, root = setup
    start = len(db.received_queries)

    engine.operation_router.run("ekg_analysis.new", [root.id], {"name": "a1", "filters": [EXCLUDE_SHIP]})

    texts = db.texts(start)
    counted = texts.index(COUNT_NODES)
    filtered = next(index for index, text in enumerate(texts) if "{ActivityName: $activity}" in text)
    # Between the counts before and the first filter: "analysis.before_apply".
    assert DELETE_CLASSES in texts[counted:filtered] and COUNT_CLASSES in texts[counted:filtered]

    ekg_analysis_sources = (bundled_module("ekg_analysis", "service").__file__,
                            bundled_module("ekg_analysis", "filters").__file__,
                            bundled_module("ekg_analysis", "operations").__file__)
    for path in ekg_analysis_sources:
        with open(path, encoding="utf-8") as source:
            assert "Class" not in source.read(), path


def test_class_nodes_left_after_the_deletion_cancel_the_analysis(setup, tmp_path):
    engine, db, root = setup
    db.set_response(COUNT_CLASSES, [{"count": 2}])
    before = [item.id for item in engine.core_tools.catalog().list()]

    with pytest.raises(DomainError, match="2 Class nodes"):
        engine.operation_router.run("ekg_analysis.new", [root.id], {"name": "a1", "filters": [EXCLUDE_SHIP]})

    assert [item.id for item in engine.core_tools.catalog().list()] == before
    assert not (tmp_path / "volume" / "orders" / "Analyses" / "a1.json").exists()
    assert _state(engine) == root.meta["graph_key"]


def test_with_the_package_disabled_the_analysis_works_and_ekg_class_has_nothing(setup):
    engine, db, root = setup
    obj = _build(engine, root)
    engine.package_manager.disable("ekg_class_graph")

    start = len(db.received_queries)
    [analysis] = engine.operation_router.run("ekg_analysis.new", [root.id], {"name": "a1", "filters": [EXCLUDE_SHIP]})
    assert analysis.meta["result"] == "unchanged"
    assert DELETE_CLASSES not in db.texts(start)

    assert engine.operation_router.operations_for([obj.id]) == []
    assert engine.visualizer_router.visualizers_for(obj.id) == []
    assert engine.export_router.exporters_for(obj.id) == []
    assert "ekg_class_graph.build" not in [entry.key for entry in engine.operation_router.operations_for([root.id])]
    groups = [group["group"] for group in engine.visualizer_router.data("ekg_views.queries", root.id, {})["groups"]]
    assert "Grafo aggregato" not in groups


def _part_labels(engine, obj_id):
    [parts] = engine.export_router.fields("ekg_views.json", obj_id)
    return [choice.label for choice in parts.choices]


def test_on_an_ekg_only_the_standard_queries_and_parts(setup):
    engine, _db, root = setup

    groups = {group["group"]: group["queries"] for group in engine.visualizer_router.data("ekg_views.queries", root.id, {})["groups"]}
    assert "Grafo aggregato" not in groups and "Conteggi" in groups
    assert _part_labels(engine, root.id) == ["Event nodes", "Entity nodes", "CORR relationships", "DF relationships"]
    views = engine.visualizer_router.data("ekg_views.graph", root.id, {})["views"]
    assert [view["key"] for view in views] == ["standard"]
    with pytest.raises(NotFoundError):
        engine.visualizer_router.action("ekg_views.queries", root.id, "query", {"key": "class.nodes"})


def test_on_an_ekg_class_the_standard_queries_and_parts_and_the_classes(setup):
    engine, db, root = setup
    obj = _build(engine, root)

    assert [entry.key for entry in engine.visualizer_router.visualizers_for(obj.id)] == [
        "ekg_class_graph.graph", "ekg_views.queries", "ekg_class_graph.stats"]
    groups = {group["group"]: group["queries"] for group in engine.visualizer_router.data("ekg_views.queries", obj.id, {})["groups"]}
    assert [query["key"] for query in groups["Grafo aggregato"]] == [
        "class.nodes", "class.obs", "class.dfc", "class.count_nodes", "class.count_obs", "class.count_dfc"]
    assert "Conteggi" in groups
    result = engine.visualizer_router.action("ekg_views.queries", obj.id, "query", {"key": "class.dfc", "params": {}})
    assert result["label"] == "Relazioni DF_C"
    assert any("MATCH (a:`Class`)-[r:`DF_C`]->(b:`Class`)" in text for text in db.texts())

    assert _part_labels(engine, obj.id) == ["Event nodes", "Entity nodes", "CORR relationships", "DF relationships",
                                            "Class nodes", "OBS relationships", "DF_C relationships"]


def test_the_class_json_parts_are_exported_under_their_own_keys(setup):
    engine, db, root = setup
    obj = _build(engine, root)
    db.set_response("""
            MATCH (a:`Event`)-[r:`OBSERVED`]->(b:`Class`)
            RETURN properties(a) AS event, type(r) AS relation_type, properties(b) AS related_event""",
                    [{"event": {"ActivityName": "Create"}, "relation_type": "OBSERVED", "related_event": {"Event_Id": "c_o1"}}])

    exported = engine.export_router.export("ekg_views.json", obj.id,
                                           {"parts": ["class_nodes", "obs", "dfc", "corr"]})

    content = json.loads(exported.content)
    assert list(content) == ["Class nodes", "OBS relationships", "DF_C relationships", "CORR relationships"]
    assert content["OBS relationships"] == {"obs_data": [{"event": {"ActivityName": "Create"}, "relation_type": "OBSERVED",
                                                          "related_event": {"Event_Id": "c_o1"}, "relation_id": 1}],
                                            "obs_count": 1}
    assert content["DF_C relationships"] == {"dfc_data": [], "dfc_count": 0}
    assert content["CORR relationships"] == {"corr_data": [], "corr_count": 0}


def test_the_aggregate_graph_draws_the_class_view_first(setup):
    engine, db, root = setup
    obj = _build(engine, root)
    db.set_response(
        classes_view_query(),
        [{"source_id": 1, "source_labels": ["Class"], "source": {"Event_Id": "c_o1_i1", "Type": "Class", "Count": 2,
                                                                 "order": "o1", "item": "i1"},
          "edge_id": 9, "edge_type": "DF_C", "edge": {"Type": "order", "edge_weight": 4},
          "target_id": 2, "target_labels": ["Class"], "target": {"Event_Id": "c_o1_i2", "Type": "Class", "order": "o1", "item": "i2"}}],
    )

    data = engine.visualizer_router.data("ekg_class_graph.graph", obj.id, {})

    assert [view["key"] for view in data["views"]] == ["class", "standard"]
    assert (data["view"], data["relations"]) == ("class", ["DF_C"])
    nodes = {node["id"]: node for node in data["graph"]["nodes"]}
    assert (nodes["1"]["label"], nodes["1"]["group"]) == ("i1 / o1", "Class")
    [edge] = data["graph"]["edges"]
    assert (edge["group"], edge["label"], edge["props"]["weight"]) == ("order", "order", 4)
    assert engine.visualizer_router.action("ekg_class_graph.graph", obj.id, "graph", {"view": "standard"})["view"] == "standard"


def classes_view_query() -> str:
    view = bundled_module("ekg_class_graph", "views").ClassGraphView()
    return view.edges_query(200, ["DF_C"]).text


def test_the_statistics_of_the_aggregate_graph(setup):
    engine, db, root = setup
    obj = _build(engine, root)
    db.set_response(COUNT_CLASSES, [{"count": 4}])
    db.set_response(classes.count_relationships_query("OBSERVED").text, [{"count": 6}])

    data = engine.visualizer_router.data("ekg_class_graph.stats", obj.id, {})

    assert data["counts"] == {"class_nodes": 4, "obs_rel": 6, "dfc_rel": 0}
    assert data["entity_types"] == ["order", "item"]
    assert data["charts"]["data"] == {"chart": "pie", "labels": ["Class Nodes", "OBS", "DF_C"],
                                      "datasets": [{"label": "numero", "data": [4, 6, 0]}]}
    assert data["charts"]["process"]["labels"] == ["Class queries", "OBS queries", "DF_C queries"]
    assert data["notice"] is None
