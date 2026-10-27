"""
------------------------------------------------------------------------
File : test_tool_packages.py
Description: The memgraph and storage tools as seen by the engine and by
             the /api/v2 routes, now served by the ekg packages (commit
             8): a package reaches the memgraph tool only if it declares
             it; without tool_memgraph the engine starts, the report says
             which packages could not load, and the v2 routes answer 503;
             POST /api/v2/graph works as before through the csv_ekg
             importer (same files under <root>/<name>/, same LOAD CSV
             paths, an "ekg" object in the catalog that becomes the active
             graph); POST /api/v2/complete-graph/build rebuilds through
             the ekg package's ensure_loaded; a legacy route that may
             change the graph makes the memgraph tool forget its state.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import io
import json

import pytest

from soup.api.flask_app import build_flask_app
from soup.core.contracts import PluginContext, SoupPlugin, ToolNotDeclaredError
from soup.core.engine import build_engine
from soup.core.settings import Settings
from tests.fakes import FakeDatabase, ekg_engine, volume_files
from tests.packages import bundled_api

MemgraphTool = bundled_api("tool_memgraph").MemgraphTool


class _AskingPackage(SoupPlugin):
    """Asks for the memgraph tool during register() and records what it got."""

    version = "1.0.0"

    def __init__(self, name: str, requires_tools=()):
        self.name = name
        self.requires_tools = tuple(requires_tools)
        self.got = None
        self.error = None

    def register(self, ctx: PluginContext) -> None:
        try:
            self.got = ctx.tools.typed("memgraph", MemgraphTool)
        except Exception as exc:  # noqa: BLE001 - recorded for the assertions
            self.error = exc


def _settings(tmp_path, packages: str) -> Settings:
    return Settings.from_env({"SOUP_PACKAGES": packages, "SOUP_INSTALLED_PACKAGES_DIR": str(tmp_path)})


def _graph_form(name: str = "orders", **extra) -> dict:
    with open("tests/fixtures/sample_event_log.csv", "rb") as stream:
        content = stream.read()
    return {
        "file": (io.BytesIO(content), "sample_event_log.csv"),
        "dataset_name": name,
        "dataset_description": "desc",
        "all_columns": json.dumps([" EventID ", "Activity", " Timestamp", "Resource ", " Order_Id", "Items"]),
        "standardColumn": json.dumps([" EventID ", " Timestamp", "Activity"]),
        "filteredColumn": json.dumps(["Items"]),
        "valuesColumn": json.dumps(["Resource "]),
        **extra,
    }


# ---------------------------------------------------------------------- #
# Declaring the tool
# ---------------------------------------------------------------------- #

def test_a_package_that_does_not_declare_memgraph_gets_an_error_asking_for_it(tmp_path):
    undeclared = _AskingPackage("undeclared")
    declared = _AskingPackage("declared", requires_tools=("memgraph",))

    engine = build_engine(_settings(tmp_path, "tool_memgraph"), extra_plugins=[undeclared, declared])

    assert isinstance(undeclared.error, ToolNotDeclaredError)
    assert "memgraph" in str(undeclared.error)
    assert undeclared.got is None
    assert declared.error is None
    assert declared.got is engine.ctx.tool_registry.get("memgraph")


def test_without_tool_memgraph_the_engine_starts_and_the_report_says_what_is_missing(tmp_path, monkeypatch):
    needs_it = _AskingPackage("needs_memgraph", requires_tools=("memgraph",))

    engine = ekg_engine(
        tmp_path, monkeypatch, packages=("tool_storage", "soup_base", "csv_table", "ekg", "csv_ekg"),
        extra_plugins=[needs_it],
    )

    assert {"tool_storage", "soup_base", "csv_table"} <= set(engine.report.loaded)
    failures = {failure.plugin_name: str(failure.error) for failure in engine.report.failed}
    assert "tool_memgraph" in failures["ekg"]
    assert "ekg" in failures["csv_ekg"]
    assert "memgraph" in failures["needs_memgraph"]


def test_without_tool_memgraph_the_legacy_routes_answer_503(tmp_path, monkeypatch):
    engine = ekg_engine(tmp_path, monkeypatch, packages=("tool_storage", "soup_base", "csv_table", "ekg", "csv_ekg"))
    client = build_flask_app(engine).test_client()

    assert client.get("/api/v2/memgraph-connect").status_code == 503
    response = client.post("/api/v2/graph", data=_graph_form(), content_type="multipart/form-data")
    assert response.status_code == 503
    assert "csv_ekg" in response.get_json()["message"]
    assert volume_files(tmp_path) == []


# ---------------------------------------------------------------------- #
# The v2 routes on the ekg packages
# ---------------------------------------------------------------------- #

@pytest.fixture
def legacy(tmp_path, monkeypatch):
    db = FakeDatabase()
    engine = ekg_engine(tmp_path, monkeypatch, db=db)
    assert engine.report.failed == []
    return engine, db, tmp_path


def _ekg_objects(engine):
    return [obj for obj in engine.core_tools.catalog().list() if obj.kind == "ekg"]


def test_post_graph_works_as_before_on_the_tools(legacy):
    engine, db, tmp_path = legacy
    client = build_flask_app(engine).test_client()

    response = client.post("/api/v2/graph", data=_graph_form(), content_type="multipart/form-data")

    assert response.status_code == 201
    assert response.get_json() == {"http_status_code": 201, "message": "Create graph successfully", "response_data": "success"}
    assert volume_files(tmp_path) == ["orders/orders.csv", "orders/orders_config.json", "orders/orders_entity.csv"]
    storage = engine.ctx.tool_registry.get("storage")
    load_queries = [q.text for q in db.received_queries if q.text.startswith("LOAD CSV FROM")]
    assert any(storage.path_for("orders", "orders.csv").replace("\\", "\\\\") in text for text in load_queries)
    assert any(storage.path_for("orders", "orders_entity.csv").replace("\\", "\\\\") in text for text in load_queries)
    config = json.loads((tmp_path / "volume" / "orders" / "orders_config.json").read_text(encoding="utf-8"))
    assert (config["dataset_name"], config["dataset_description"]) == ("orders", "desc")
    assert config["all_columns"] == ["EventID", "Activity", "Timestamp", "Resource", "Order_Id", "Items"]
    # The dataset is now an "ekg" object of the catalog, created by csv_ekg.
    [obj] = _ekg_objects(engine)
    assert (obj.name, obj.description, obj.meta["dataset"], obj.created_by.contributor_id) == (
        "orders", "desc", "orders", "csv_ekg.csv",
    )


def test_post_graph_translates_trigger_target_and_process_execution(legacy):
    engine, db, tmp_path = legacy
    form = _graph_form(
        filteredColumn=json.dumps(["Items", " Order_Id"]), trigger_0=" Order_Id", target_0="Items", process_execution="true",
    )

    response = build_flask_app(engine).test_client().post("/api/v2/graph", data=form, content_type="multipart/form-data")

    assert response.status_code == 201
    config = json.loads((tmp_path / "volume" / "orders" / "orders_config.json").read_text(encoding="utf-8"))
    assert config["trigger_target_rows"] == [{"trigger": "Order_Id", "target": "Items"}]
    assert config["process_info"]["init_df_time"] is not None
    assert any(q.params == {"trigger": "Order_Id", "target": "Items"} for q in db.received_queries)


def test_post_graph_with_a_wrong_standard_column_is_400(legacy):
    engine, _db, tmp_path = legacy

    response = build_flask_app(engine).test_client().post(
        "/api/v2/graph", data=_graph_form(standardColumn=json.dumps(["a", "b"])), content_type="multipart/form-data"
    )

    assert response.status_code == 400
    assert "standardColumn" in response.get_json()["message"]
    assert volume_files(tmp_path) == []


def test_memgraph_connect_pings_the_tool(legacy):
    engine, db, _tmp_path = legacy
    db.set_default_response([{"1": 1}])

    response = build_flask_app(engine).test_client().get("/api/v2/memgraph-connect")

    assert response.status_code == 200
    assert db.received_queries[-1].text == "RETURN 1"


def test_the_v2_import_makes_its_object_the_active_graph(legacy):
    engine, _db, _tmp_path = legacy
    tool = engine.ctx.tool_registry.get("memgraph")
    tool.ensure_loaded("some-object", lambda run: None)

    response = build_flask_app(engine).test_client().post(
        "/api/v2/graph", data=_graph_form(), content_type="multipart/form-data"
    )

    assert response.status_code == 201
    [obj] = _ekg_objects(engine)
    assert tool.current_state() == obj.meta["graph_key"]


def test_hostile_dataset_name_is_refused(legacy):
    engine, _db, tmp_path = legacy

    response = build_flask_app(engine).test_client().post(
        "/api/v2/graph", data=_graph_form("_catalog"), content_type="multipart/form-data"
    )

    assert response.status_code == 400
    assert volume_files(tmp_path) == []


def test_complete_graph_build_rebuilds_through_ensure_loaded(legacy):
    engine, db, _tmp_path = legacy
    client = build_flask_app(engine).test_client()
    client.post("/api/v2/graph", data=_graph_form(), content_type="multipart/form-data")
    resets = []
    engine.ctx.event_bus.subscribe("ekg.before_reset", lambda payload: resets.append(dict(payload)), owner="test")
    start = len(db.received_queries)

    response = client.post("/api/v2/complete-graph/build", json={"dataset_name": "orders"})

    assert response.status_code == 200
    assert response.get_json()["response_data"] == "success"
    assert response.get_json()["message"] == "Successfully created the Dataset graphs"
    texts = [q.text for q in db.received_queries[start:]]
    # Rebuilt even though it was the active graph: the old pages change it outside the tool.
    assert texts[0] == "MATCH (n) DETACH DELETE n"
    assert any(text.startswith("LOAD CSV") for text in texts)
    [obj] = _ekg_objects(engine)
    assert [(reset["object"], reset["reason"]) for reset in resets] == [(obj.id, "load")]
    assert engine.ctx.tool_registry.get("memgraph").current_state() == obj.meta["graph_key"]


def test_complete_graph_build_of_an_unknown_dataset_is_404(legacy):
    engine, db, _tmp_path = legacy

    response = build_flask_app(engine).test_client().post("/api/v2/complete-graph/build", json={"dataset_name": "nope"})

    assert response.status_code == 404
    assert response.get_json()["message"] == "Unable to create the Dataset graphs"
    assert db.received_queries == []


def test_a_legacy_route_that_may_change_the_graph_makes_the_tool_forget_its_state(legacy):
    engine, _db, _tmp_path = legacy
    app = build_flask_app(engine)
    app.add_url_rule("/api/v2/test-change", "test_change", lambda: ("", 204), methods=["POST", "GET"])
    tool = engine.ctx.tool_registry.get("memgraph")
    client = app.test_client()

    tool.ensure_loaded("some-object", lambda run: None)
    client.get("/api/v2/test-change")
    assert tool.current_state() == "some-object"

    client.post("/api/v2/test-change")
    assert tool.current_state() is None
