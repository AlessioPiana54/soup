"""
------------------------------------------------------------------------
File : test_api_v3_system.py
Description: Tests for /api/v3/preferences, /tools and /health
             (soup/api/system_routes.py, SystemService): preferences
             read/write with validated keys and 503 without the tool,
             the tools with their package and health, health "ok" or
             "degraded" (a tool not ok or raising, a missing core tool, a
             failed package), and the v2 routes still served by the same
             app.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import io

from soup.core.settings import Settings
from tests.api_client import client_for, code_client, data_of, disk_client
from tests.fakes import CoreToolsPackage, fake_tool_engine
from tests.mediator_doubles import FakeTool, FeaturePackage
from tests.package_builder import FAILING_PLUGIN, write_package


class _SickTool(FakeTool):
    def health(self):
        return {"ok": False, "error": "connection refused"}


class _RaisingTool(FakeTool):
    def health(self):
        raise RuntimeError("boom")


def test_preferences():
    client, _, core = code_client()

    assert data_of(client.get("/api/v3/preferences/theme")) == {"key": "theme", "value": None}
    saved = client.put("/api/v3/preferences/theme", json={"value": {"dark": True}})
    assert saved.status_code == 200
    assert core.preferences.values == {"theme": {"dark": True}}
    assert data_of(client.get("/api/v3/preferences/theme"))["value"] == {"dark": True}

    assert client.put("/api/v3/preferences/theme", json={"other": 1}).status_code == 400
    assert client.put("/api/v3/preferences/theme", data="x", content_type="application/json").status_code == 400
    assert client.get("/api/v3/preferences/_secret").status_code == 400
    assert client.get("/api/v3/preferences/a..b").status_code == 400


def test_preferences_without_the_tool_are_503():
    client, _, _ = code_client(with_core_tools=False)

    assert client.get("/api/v3/preferences/theme").status_code == 503


def test_tools_and_healthy_server():
    client, _, _ = code_client(FeaturePackage("extra", tools=[FakeTool("cache")]))

    tools = data_of(client.get("/api/v3/tools"))
    assert [(tool["name"], tool["package"], tool["ok"]) for tool in tools] == [
        ("cache", "extra", True),
        ("catalog", "test_core_tools", True),
        ("preferences", "test_core_tools", True),
    ]
    health = data_of(client.get("/api/v3/health"))
    # The legacy "memgraph"/"storage" tools are not loaded here.
    assert health["status"] == "degraded"
    assert any("'memgraph'" in problem for problem in health["problems"])


def test_health_ok_with_every_tool():
    engine = fake_tool_engine(Settings.from_env({"SOUP_PACKAGES": ""}), extra_plugins=[CoreToolsPackage()])
    client = client_for(engine)

    response = client.get("/api/v3/health")

    assert response.status_code == 200
    assert data_of(response)["status"] == "ok"
    assert data_of(response)["problems"] == []


def test_health_degraded_by_sick_tools_and_failed_packages(tmp_path):
    write_package(tmp_path / "bundled", "broken", plugin_source=FAILING_PLUGIN)
    client, _ = disk_client(
        tmp_path, extra_plugins=[FeaturePackage("extra", tools=[_SickTool("db"), _RaisingTool("bad")])]
    )

    health = data_of(client.get("/api/v3/health"))
    tools = {tool["name"]: tool for tool in health["tools"]}

    assert health["status"] == "degraded"
    assert tools["db"]["health"] == {"ok": False, "error": "connection refused"}
    assert tools["bad"]["ok"] is False
    assert "boom" in tools["bad"]["health"]["error"]
    assert any("broken" in problem for problem in health["problems"])
    assert any("connection refused" in problem for problem in health["problems"])


def test_v2_routes_are_still_served():
    client, _, _ = code_client()

    assert client.get("/api/v2/welcome").status_code == 200
    # Without the "memgraph" tool, memgraph-connect answers 503 as before.
    assert client.get("/api/v2/memgraph-connect").status_code == 503
    no_file = client.post("/api/v2/graph", data={}, content_type="multipart/form-data")
    assert no_file.status_code == 400
    assert no_file.get_json()["message"] == "Bad request. File not found"
    legacy = client.post("/api/v2/graph", data={"file": (io.BytesIO(b"a"), "x.csv")},
                         content_type="multipart/form-data")
    assert legacy.status_code != 404
