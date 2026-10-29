"""
------------------------------------------------------------------------
File : test_ekg_views_extensibility.py
Description: ekg_views is extended without being modified: a test package
             written on disk (views_test, requires ekg_views) contributes
             a GraphQuery to "ekg.queries", a GraphView to
             "ekg.graph_views", a JsonPart to "ekg.json_parts" and a
             StatsNotice to "ekg.stats_notices"; they appear in
             Interrogazioni, in the views of Grafo, among the parts of the
             JSON export and in the notice of Statistiche, and disappear
             when the package is disabled. In the host: an "ekg" object offers the three
             visualizers (also through GET /api/v3/objects/<id>/visualizers)
             and the JSON export in the format of /api/v2/json/graph/*;
             "table" and "text" objects get no EKG visualizer or exporter.
Project : soup-packages/ekg_views
------------------------------------------------------------------------
"""

from __future__ import annotations

import json
import textwrap

import pytest

from soup.core.contracts import NotFoundError, Upload, ValidationError
from tests.fakes import EKG_PACKAGES, FakeDatabase, ekg_engine

CSV = b"case,activity,time,order\n1,Create,2021-01-01T10:00:00.000,o1\n2,Ship,2021-01-01T11:00:00.000,o1\n"
OPTIONS = {"event_id": "case", "timestamp": "time", "activity": "activity", "entities": ["order"]}

MANIFEST = {
    "name": "views_test",
    "version": "1.0.0",
    "api_version": "4.0",
    "requires": ["ekg", "ekg_views"],
    "requires_tools": [],
    "server": {"module": "server", "plugin": "plugin:Plugin"},
}

PLUGIN = '''
from soup.core.contracts import Field, PluginContext, SoupPlugin, report
from soup_pkg_ekg.api import Query
from soup_pkg_ekg_views.api import (
    GRAPH_VIEWS_POINT, JSON_PARTS_POINT, QUERIES_POINT, STATS_NOTICES_POINT, EdgeListGraphView, GraphQuery, NodesPart,
    StatsNotice,
)


class OnlyDf(EdgeListGraphView):
    key = "only_df"
    label = "Solo DF"
    relationships = {"DF": ("Event", "Event")}
    default_relations = ("DF",)


class Echo(GraphQuery):
    key = "test.echo"
    label = "Eco"
    group = "Test"
    fields = (Field("word", "Parola", required=True),)

    def build(self, params):
        return Query("RETURN $word AS word", {"word": params["word"]})

    def transform(self, records, params):
        return [report.text(str(records[0]["word"]) if records else "", title="Eco")]


class OrdersNotice(StatsNotice):
    key = "test.orders"

    def notice(self, obj, tools):
        return "Un avviso del test." if obj.name == "orders" else None


class Plugin(SoupPlugin):
    def register(self, ctx: PluginContext) -> None:
        ctx.contribute(STATS_NOTICES_POINT, OrdersNotice(), key=OrdersNotice.key)
        ctx.contribute(GRAPH_VIEWS_POINT, OnlyDf(), key=OnlyDf.key)
        ctx.contribute(QUERIES_POINT, Echo(), key=Echo.key)
        ctx.contribute(JSON_PARTS_POINT, NodesPart("class_nodes", "Class nodes", "Class"), key="class_nodes")
'''


def _write_package(root) -> None:
    folder = root / "views_test"
    (folder / "server").mkdir(parents=True)
    (folder / "soup-package.json").write_text(json.dumps(MANIFEST), encoding="utf-8")
    (folder / "server" / "__init__.py").write_text("", encoding="utf-8")
    (folder / "server" / "plugin.py").write_text(textwrap.dedent(PLUGIN), encoding="utf-8")


@pytest.fixture
def setup(tmp_path, monkeypatch):
    _write_package(tmp_path / "installed")
    db = FakeDatabase()
    engine = ekg_engine(tmp_path, monkeypatch, packages=(*EKG_PACKAGES, "text", "views_test"), db=db)
    assert engine.report.failed == [], engine.report.failed
    return engine, db


def _import_ekg(engine):
    return engine.import_router.import_("csv_ekg.csv", Upload.from_bytes("orders.csv", CSV), "orders", options=OPTIONS)


def test_a_query_of_another_package_appears_in_interrogazioni(setup):
    engine, db = setup
    obj = _import_ekg(engine)

    groups = {group["group"]: group["queries"] for group in engine.visualizer_router.data("ekg_views.queries", obj.id, {})["groups"]}
    assert [query["key"] for query in groups["Test"]] == ["test.echo"]
    assert groups["Test"][0]["fields"][0]["name"] == "word"
    assert len(groups["Conteggi"]) == 5

    db.set_response("RETURN $word AS word", [{"word": "ciao"}])
    result = engine.visualizer_router.action("ekg_views.queries", obj.id, "query", {"key": "test.echo", "params": {"word": "ciao"}})
    assert result["blocks"] == [{"type": "text", "title": "Eco", "data": {"text": "ciao"}}]
    assert db.received_queries[-1].params == {"word": "ciao"}

    with pytest.raises(ValidationError, match="word"):
        engine.visualizer_router.action("ekg_views.queries", obj.id, "query", {"key": "test.echo", "params": {}})
    with pytest.raises(NotFoundError):
        engine.visualizer_router.action("ekg_views.queries", obj.id, "query", {"key": "nope"})


def test_a_view_of_another_package_disappears_with_its_package(setup):
    engine, db = setup
    obj = _import_ekg(engine)

    data = engine.visualizer_router.data("ekg_views.graph", obj.id, {})
    assert [view["key"] for view in data["views"]] == ["standard", "object", "only_df"]
    result = engine.visualizer_router.action("ekg_views.graph", obj.id, "graph", {"view": "only_df"})
    assert result["view"] == "only_df"
    assert "MATCH (a:`Event`)-[r:`DF`]->(b:`Event`)" in db.received_queries[-2].text

    engine.package_manager.disable("views_test")

    data = engine.visualizer_router.data("ekg_views.graph", obj.id, {})
    assert [view["key"] for view in data["views"]] == ["standard", "object"]
    with pytest.raises(ValidationError, match="view"):
        engine.visualizer_router.action("ekg_views.graph", obj.id, "graph", {"view": "only_df"})
    groups = [group["group"] for group in engine.visualizer_router.data("ekg_views.queries", obj.id, {})["groups"]]
    assert "Test" not in groups


def test_a_notice_of_another_package_is_shown_by_the_statistics_until_it_is_disabled(setup):
    engine, _db = setup
    obj = _import_ekg(engine)
    other = engine.import_router.import_("csv_ekg.csv", Upload.from_bytes("other.csv", CSV), "other", options=OPTIONS)

    assert engine.visualizer_router.data("ekg_views.stats", obj.id, {})["notice"] == "Un avviso del test."
    assert engine.visualizer_router.data("ekg_views.stats", other.id, {})["notice"] is None

    engine.package_manager.disable("views_test")

    assert engine.visualizer_router.data("ekg_views.stats", obj.id, {})["notice"] is None


def test_a_json_part_of_another_package_is_exported_under_its_own_key(setup):
    engine, db = setup
    obj = _import_ekg(engine)

    [field] = engine.export_router.fields("ekg_views.json", obj.id)
    assert field.type == "multiselect"
    assert [(choice.value, choice.label) for choice in field.choices] == [
        ("event_nodes", "Event nodes"), ("entity_nodes", "Entity nodes"), ("corr", "CORR relationships"),
        ("df", "DF relationships"), ("rel", "REL relationships"), ("class_nodes", "Class nodes"),
    ]

    db.set_default_response([{"node": {"Name": "Create"}}])
    exported = engine.export_router.export("ekg_views.json", obj.id, {"parts": ["class_nodes"]})
    assert json.loads(exported.content) == {"Class nodes": [{"Name": "Create"}]}
    assert "MATCH (n:`Class`)" in db.received_queries[-1].text


def test_the_json_export_has_the_v2_format(setup):
    engine, db = setup
    obj = _import_ekg(engine)
    event = {"Event_Id": "1", "ActivityName": "Create"}
    db.set_default_response([{"node": event, "event": event, "relation_type": "DF", "related_event": event}])

    exported = engine.export_router.export("ekg_views.json", obj.id, {"parts": ["event_nodes", "corr", "df"]})

    assert (exported.filename, exported.mime) == ("orders.json", "application/json")
    content = json.loads(exported.content)
    assert list(content) == ["Event nodes", "CORR relationships", "DF relationships"]
    assert content["Event nodes"] == [event]
    assert content["CORR relationships"]["corr_count"] == 1
    assert content["DF relationships"] == {
        "df_data": [{"event": event, "relation_type": "DF", "related_event": event, "relation_id": 1}], "df_count": 1,
    }
    with pytest.raises(ValidationError):
        engine.export_router.export("ekg_views.json", obj.id, {"parts": ["nope"]})


def test_an_ekg_object_shows_the_three_visualizers(setup):
    from soup.api.flask_app import build_flask_app

    engine, _db = setup
    obj = _import_ekg(engine)

    entries = engine.visualizer_router.visualizers_for(obj.id)
    ekg_views = sorted((entry.key, entry.item.element) for entry in entries if entry.package == "ekg_views")
    assert ekg_views == [
        ("ekg_views.graph", "soup-pkg-ekg-graph"),
        ("ekg_views.queries", "soup-pkg-ekg-queries"),
        ("ekg_views.stats", "soup-pkg-ekg-stats"),
    ]
    assert "ekg_views.json" in [entry.key for entry in engine.export_router.exporters_for(obj.id)]

    response = build_flask_app(engine).test_client().get(f"/api/v3/objects/{obj.id}/visualizers")
    assert response.status_code == 200
    listed = {item["label"]: item for item in response.get_json()["response_data"]}
    assert {"Grafo", "Statistiche", "Interrogazioni"} <= set(listed)
    assert listed["Grafo"]["module_url"].startswith("/api/v3/packages/ekg_views/app/")


def test_no_ekg_visualizer_or_exporter_for_tables_and_texts(setup):
    engine, _db = setup
    table = engine.import_router.import_("csv_table.csv", Upload.from_bytes("orders.csv", CSV), "table")
    text = engine.import_router.import_("text.text", Upload.from_bytes("notes.txt", b"hello"), "notes")

    for obj in (table, text):
        assert [entry.key for entry in engine.visualizer_router.visualizers_for(obj.id) if entry.package == "ekg_views"] == []
        assert [entry.key for entry in engine.export_router.exporters_for(obj.id) if entry.package == "ekg_views"] == []
        with pytest.raises(NotFoundError):
            engine.visualizer_router.data("ekg_views.graph", obj.id, {})
