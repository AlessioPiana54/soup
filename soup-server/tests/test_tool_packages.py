"""
------------------------------------------------------------------------
File : test_tool_packages.py
Description: The memgraph and storage tools as seen by the engine: a
             package reaches the memgraph tool only if it declares it;
             without tool_memgraph the engine starts and the report says
             what is missing; POST /api/v2/graph works as before on the
             in-memory tools (same files under /soup/<name>/, same LOAD
             CSV paths) and answers 503 without them; the legacy import
             invalidates the memgraph tool's active state.
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
from tests.fakes import FakeDatabase, InMemoryFileStorage, fake_tool_engine
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


def _graph_form(name: str = "orders") -> dict:
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


def test_without_tool_memgraph_the_engine_starts_and_the_report_says_what_is_missing(tmp_path):
    needs_it = _AskingPackage("needs_memgraph", requires_tools=("memgraph",))

    engine = build_engine(_settings(tmp_path, "csv_reader,tool_storage"), extra_plugins=[needs_it])

    assert {"csv_reader", "tool_storage"} <= set(engine.report.loaded)
    assert any("'memgraph' tool" in warning and "/api/v2/graph" in warning for warning in engine.report.warnings)
    [failure] = [failure for failure in engine.report.failed if failure.plugin_name == "needs_memgraph"]
    assert "memgraph" in str(failure.error)


def test_without_tool_memgraph_the_legacy_routes_answer_503(tmp_path):
    engine = build_engine(_settings(tmp_path, "csv_reader"))
    client = build_flask_app(engine).test_client()

    assert client.get("/api/v2/memgraph-connect").status_code == 503
    response = client.post("/api/v2/graph", data=_graph_form(), content_type="multipart/form-data")
    assert response.status_code == 503
    # The files are staged first, so the missing storage tool is what stops it.
    assert "'storage' tool" in response.get_json()["message"]


# ---------------------------------------------------------------------- #
# The legacy import on the tools
# ---------------------------------------------------------------------- #

@pytest.fixture
def legacy(tmp_path):
    db, files = FakeDatabase(), InMemoryFileStorage()
    engine = fake_tool_engine(_settings(tmp_path, "csv_reader"), db=db, files=files)
    return engine, db, files


def test_post_graph_works_as_before_on_the_tools(legacy):
    engine, db, files = legacy
    client = build_flask_app(engine).test_client()

    response = client.post("/api/v2/graph", data=_graph_form(), content_type="multipart/form-data")

    assert response.status_code == 201
    assert response.get_json()["message"] == "Create graph successfully"
    assert files.paths == ["orders/orders.csv", "orders/orders_config.json", "orders/orders_entity.csv"]
    load_queries = [q.text for q in db.received_queries if q.text.startswith("LOAD CSV FROM")]
    assert any("/soup/orders/orders.csv" in text for text in load_queries)
    assert any("/soup/orders/orders_entity.csv" in text for text in load_queries)
    assert engine.repository.load_config("orders")["dataset_name"] == "orders"


def test_memgraph_connect_pings_the_tool(legacy):
    engine, db, _files = legacy
    db.set_default_response([{"1": 1}])

    response = build_flask_app(engine).test_client().get("/api/v2/memgraph-connect")

    assert response.status_code == 200
    assert db.received_queries[-1].text == "RETURN 1"


def test_legacy_import_invalidates_the_active_graph(legacy):
    engine, _db, _files = legacy
    tool = engine.ctx.tool_registry.get("memgraph")
    tool.ensure_loaded("some-object", lambda run: None)

    response = build_flask_app(engine).test_client().post(
        "/api/v2/graph", data=_graph_form(), content_type="multipart/form-data"
    )

    assert response.status_code == 201
    assert tool.current_state() is None


def test_hostile_dataset_name_is_refused(legacy):
    engine, _db, files = legacy

    response = build_flask_app(engine).test_client().post(
        "/api/v2/graph", data=_graph_form("_catalog"), content_type="multipart/form-data"
    )

    assert response.status_code == 400
    assert files.paths == []
