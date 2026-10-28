"""
------------------------------------------------------------------------
File : test_default_packages_api.py
Description: The app as docker compose starts it: no package selection
             (every bundled package), tool_storage on a local folder and
             the memgraph tool on a FakeDatabase (no Docker, no
             Memgraph). GET /api/v3/packages lists all the bundled
             packages as active - none failed, missing or disabled - and
             /api/v3/health finds every tool the core relies on.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from soup.core.engine import build_engine
from soup.core.settings import Settings
from tests.api_client import client_for
from tests.fakes import FakeDatabase, use_database
from tests.packages import BUNDLED_PACKAGES_DIR

BUNDLED = [
    "causal_df", "csv_ekg", "csv_table", "ekg", "ekg_analysis", "ekg_class_graph", "ekg_views", "ocel", "soup_base",
    "text", "tool_memgraph", "tool_storage",
]


def _default_client(tmp_path, monkeypatch):
    monkeypatch.setenv("SOUP_STORAGE_KIND", "local")
    monkeypatch.setenv("SOUP_LOCAL_STORAGE_ROOT", str(tmp_path / "volume"))
    installed = tmp_path / "installed"
    settings = Settings(
        packages=None,
        packages_path=(str(BUNDLED_PACKAGES_DIR), str(installed)),
        installed_packages_dir=str(installed),
    )
    engine = build_engine(settings)
    db = FakeDatabase()
    db.set_default_response([{"ok": 1}])
    use_database(engine, db)
    return client_for(engine), engine


def test_every_default_package_is_active(tmp_path, monkeypatch):
    client, engine = _default_client(tmp_path, monkeypatch)

    response = client.get("/api/v3/packages")

    assert response.status_code == 200
    packages = {item["name"]: item for item in response.get_json()["response_data"]}
    assert sorted(packages) == BUNDLED
    rejected = {name: (item["status"], item["error"]) for name, item in packages.items() if item["status"] != "active"}
    assert rejected == {}
    assert engine.report.failed == []
    assert engine.report.warnings == []


def test_health_with_the_default_packages_finds_every_core_tool(tmp_path, monkeypatch):
    client, _engine = _default_client(tmp_path, monkeypatch)

    health = client.get("/api/v3/health").get_json()["response_data"]

    assert sorted(tool["name"] for tool in health["tools"]) == ["catalog", "memgraph", "preferences", "storage"]
    assert health["status"] == "ok", health["problems"]
