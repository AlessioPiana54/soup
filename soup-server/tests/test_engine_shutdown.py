"""
------------------------------------------------------------------------
File : test_engine_shutdown.py
Description: Tests that Engine.shutdown() shuts down the packages, and
             that the Memgraph driver - now owned by the tool_memgraph
             package - is closed when the engine shuts down or the
             package is disabled (C31), without the core knowing about it.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import importlib

import pytest

from soup.core.engine import build_engine
from soup.core.settings import Settings
from tests.fakes import FakeDatabase
from tests.packages import bundled_api


class _DatabaseWithClose(FakeDatabase):
    instances: list["_DatabaseWithClose"] = []

    def __init__(self, uri: str = "", auth: tuple = ("", "")):
        super().__init__()
        self.uri = uri
        self.closed = False
        _DatabaseWithClose.instances.append(self)

    def close(self):
        self.closed = True


@pytest.fixture
def memgraph_engine(monkeypatch, tmp_path):
    """An engine with the real tool_memgraph package, on a database that records close()."""

    bundled_api("tool_memgraph")
    plugin_module = importlib.import_module("soup_pkg_tool_memgraph.plugin")
    monkeypatch.setattr(plugin_module, "MemgraphDatabase", _DatabaseWithClose)
    _DatabaseWithClose.instances = []
    settings = Settings.from_env({"SOUP_PACKAGES": "tool_memgraph", "SOUP_INSTALLED_PACKAGES_DIR": str(tmp_path)})
    return build_engine(settings)


def test_shutdown_closes_the_memgraph_driver(memgraph_engine):
    [db] = _DatabaseWithClose.instances

    memgraph_engine.shutdown()

    assert db.closed is True


def test_disabling_tool_memgraph_closes_the_driver(memgraph_engine):
    [db] = _DatabaseWithClose.instances

    memgraph_engine.package_manager.disable("tool_memgraph")

    assert db.closed is True
    assert "memgraph" not in memgraph_engine.ctx.tool_registry


def test_tool_memgraph_connects_where_the_environment_says(memgraph_engine):
    [db] = _DatabaseWithClose.instances

    assert db.uri == "bolt://memgraph:7687"


def test_shutdown_still_shuts_down_the_plugin_manager():
    shutdown_calls = []

    from soup.core.contracts import PluginContext, SoupPlugin

    class _TrackingPlugin(SoupPlugin):
        name = "tracking_plugin_test_only"
        version = "1.0.0"

        def register(self, ctx: PluginContext) -> None:
            pass

        def on_shutdown(self, ctx: PluginContext) -> None:
            shutdown_calls.append("tracking_plugin_test_only")

    engine = build_engine(Settings.from_env({"SOUP_PACKAGES": ""}))

    # Load an extra plugin directly into the engine's own context/manager,
    # the same way build_engine wires the built-in ones.
    engine.plugin_manager.load([_TrackingPlugin()], ctx=engine.ctx)

    engine.shutdown()

    assert "tracking_plugin_test_only" in shutdown_calls
