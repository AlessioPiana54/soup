"""
------------------------------------------------------------------------
File : test_tool_packages.py
Description: The memgraph and storage tools as seen by the engine and by
             /api/v3: a package reaches the memgraph tool only if it
             declares it; without tool_memgraph the engine starts, the
             report says which packages could not load and the csv_ekg
             importer is not offered; /api/v3/health pings the tool. The
             import through csv_ekg is tested next to the package
             (soup-packages/csv_ekg/tests).
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

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


def test_without_tool_memgraph_the_csv_ekg_importer_is_not_offered(tmp_path, monkeypatch):
    engine = ekg_engine(tmp_path, monkeypatch, packages=("tool_storage", "soup_base", "csv_table", "ekg", "csv_ekg"))
    client = build_flask_app(engine).test_client()

    response = client.get("/api/v3/importers?filename=orders.csv")

    assert response.status_code == 200
    keys = {importer["id"] for importer in response.get_json()["response_data"]}
    assert "csv_table.csv" in keys
    assert "csv_ekg.csv" not in keys
    assert volume_files(tmp_path) == []


# ---------------------------------------------------------------------- #
# The memgraph tool behind /api/v3/health
# ---------------------------------------------------------------------- #

def test_health_pings_the_memgraph_tool(tmp_path, monkeypatch):
    db = FakeDatabase()
    db.set_default_response([{"ok": 1}])
    engine = ekg_engine(tmp_path, monkeypatch, db=db)
    assert engine.report.failed == []

    response = build_flask_app(engine).test_client().get("/api/v3/health")

    assert response.status_code == 200
    tools = {tool["name"]: tool for tool in response.get_json()["response_data"]["tools"]}
    assert tools["memgraph"]["ok"] is True
    assert db.received_queries[-1].text == "RETURN 1 AS ok"
