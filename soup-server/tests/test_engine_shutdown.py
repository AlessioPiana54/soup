"""
------------------------------------------------------------------------
File : test_engine_shutdown.py
Description: Tests that Engine.shutdown() closes the database when the
             concrete adapter has a close() method (MemgraphDatabase
             does), and does not blow up when it doesn't (fakes used in
             tests, and any future adapter with no such resource).
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from soup.core.engine import build_engine
from soup.core.settings import Settings
from tests.fakes import FakeDatabase, InMemoryFileStorage


class _DatabaseWithClose(FakeDatabase):
    def __init__(self):
        super().__init__()
        self.closed = False

    def close(self):
        self.closed = True


def test_shutdown_closes_the_database_when_it_has_a_close_method():
    db = _DatabaseWithClose()
    engine = build_engine(Settings.from_env({"SOUP_PACKAGES": ""}), db=db, storage=InMemoryFileStorage())

    engine.shutdown()

    assert db.closed is True


def test_shutdown_does_not_fail_when_the_database_has_no_close_method():
    # FakeDatabase (used everywhere else in the suite) has no close() -
    # shutdown() must not raise AttributeError over that.
    db = FakeDatabase()
    engine = build_engine(Settings.from_env({"SOUP_PACKAGES": ""}), db=db, storage=InMemoryFileStorage())

    engine.shutdown()  # must not raise


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

    db = FakeDatabase()
    settings = Settings.from_env({"SOUP_PACKAGES": ""})
    engine = build_engine(settings, db=db, storage=InMemoryFileStorage())

    # Load an extra plugin directly into the engine's own context/manager,
    # the same way build_engine wires the built-in ones.
    engine.plugin_manager.load([_TrackingPlugin()], ctx=engine.ctx)

    engine.shutdown()

    assert "tracking_plugin_test_only" in shutdown_calls
