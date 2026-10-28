"""
------------------------------------------------------------------------
File : test_plugin_manager.py
Description: Tests for PluginManager - dependency ordering, cycle
             detection, and isolation of faulty plugins in the
             PackageReport (soup.core.plugin_manager).
Project : soup-server
------------------------------------------------------------------------
"""

import pytest

from soup.core.contracts import (
    CONTRACTS_API_VERSION,
    Importer,
    Inspection,
    PluginApiVersionError,
    PluginConflictError,
    PluginCycleError,
    PluginDependencyError,
    SoupPlugin,
)
from soup.core.plugin_manager import PluginManager


class _Marker(Importer):
    """An importer registered only to see a package's contributions come and go."""

    extensions = (".marker",)
    produces = "marker"

    def __init__(self, marker_id):
        self.id = marker_id

    def inspect(self, upload, tools):
        return Inspection()

    def import_(self, upload, obj, options, tools):
        return {}

    def dispose(self, obj, tools):
        pass


def _mark(marker_id):
    return lambda ctx: ctx.add_importer(_Marker(marker_id))


class _Plugin(SoupPlugin):
    """Minimal concrete SoupPlugin, configurable per test case."""

    def __init__(
        self,
        name,
        version="1.0.0",
        requires=(),
        api_version=CONTRACTS_API_VERSION,
        on_register=None,
        on_shutdown_cb=None,
        extension_points=(),
    ):
        self.name = name
        self.version = version
        self.requires = tuple(requires)
        self.extension_points = tuple(extension_points)
        self.api_version = api_version
        self._on_register = on_register
        self._on_shutdown_cb = on_shutdown_cb
        self.registered = False

    def register(self, ctx):
        self.registered = True
        if self._on_register:
            self._on_register(ctx)

    def on_shutdown(self, ctx):
        if self._on_shutdown_cb:
            self._on_shutdown_cb(ctx)


def test_independent_plugins_all_register_successfully():
    manager = PluginManager()
    a = _Plugin("plugin_a", on_register=_mark("a"))
    b = _Plugin("plugin_b", on_register=_mark("b"))

    report = manager.load([a, b])

    assert sorted(report.loaded) == ["plugin_a", "plugin_b"]
    assert report.failed == []
    assert a.registered and b.registered


def test_dependency_ordering_loads_dependency_before_dependent():
    manager = PluginManager()
    load_order = []

    base = _Plugin("base", on_register=lambda ctx: load_order.append("base"))
    dependent = _Plugin(
        "dependent", requires=("base",), on_register=lambda ctx: load_order.append("dependent")
    )

    # Passed in the "wrong" order on purpose - the manager must reorder them.
    report = manager.load([dependent, base])

    assert load_order == ["base", "dependent"]
    assert report.failed == []
    assert report.loaded == ["base", "dependent"]


def test_cycle_between_two_plugins_is_detected():
    manager = PluginManager()
    x = _Plugin("x", requires=("y",))
    y = _Plugin("y", requires=("x",))

    with pytest.raises(PluginCycleError) as exc_info:
        manager.load([x, y])

    assert set(exc_info.value.cycle) == {"x", "y"}


def test_self_dependency_is_a_cycle():
    manager = PluginManager()
    looping = _Plugin("looping", requires=("looping",))

    with pytest.raises(PluginCycleError):
        manager.load([looping])


def test_four_faulty_plugins_are_isolated_without_blocking_the_good_one():
    manager = PluginManager()

    def _open_and_contribute(ctx):
        ctx.add_extension_point("inputs")
        ctx.contribute("inputs", object(), key="csv")

    good = _Plugin("good", on_register=_open_and_contribute, extension_points=("inputs",))

    def _raise(ctx):
        raise RuntimeError("boom")

    raises_exception = _Plugin("raises_exception", on_register=_raise)

    def _duplicate_key(ctx):
        ctx.contribute("inputs", object(), key="csv")  # "csv" already contributed by `good`

    duplicate_key = _Plugin("duplicate_key", on_register=_duplicate_key)

    missing_dependency = _Plugin("missing_dependency", requires=("does_not_exist",))

    incompatible_api_version = _Plugin("incompatible_api_version", api_version="99.0")

    report = manager.load(
        [good, raises_exception, duplicate_key, missing_dependency, incompatible_api_version]
    )

    assert report.loaded == ["good"]
    assert good.registered is True

    failed_by_name = {failure.plugin_name: failure.error for failure in report.failed}
    assert set(failed_by_name) == {
        "raises_exception",
        "duplicate_key",
        "missing_dependency",
        "incompatible_api_version",
    }
    assert isinstance(failed_by_name["raises_exception"], RuntimeError)
    assert isinstance(failed_by_name["duplicate_key"], PluginConflictError)
    assert isinstance(failed_by_name["missing_dependency"], PluginDependencyError)
    assert isinstance(failed_by_name["incompatible_api_version"], PluginApiVersionError)


def test_strict_mode_raises_instead_of_isolating():
    manager = PluginManager(strict=True)

    def _raise(ctx):
        raise RuntimeError("boom")

    bad = _Plugin("bad", on_register=_raise)

    with pytest.raises(RuntimeError):
        manager.load([bad])


def test_strict_mode_raises_on_missing_dependency():
    manager = PluginManager(strict=True)
    bad = _Plugin("bad", requires=("missing",))

    with pytest.raises(PluginDependencyError):
        manager.load([bad])


def test_shutdown_runs_in_reverse_load_order():
    manager = PluginManager()
    shutdown_order = []

    a = _Plugin("a", on_shutdown_cb=lambda ctx: shutdown_order.append("a"))
    b = _Plugin("b", on_shutdown_cb=lambda ctx: shutdown_order.append("b"))

    manager.load([a, b])
    manager.shutdown()

    assert shutdown_order == ["b", "a"]


def test_shutdown_skips_plugins_that_failed_to_load():
    manager = PluginManager()
    shutdown_order = []

    good = _Plugin("good", on_shutdown_cb=lambda ctx: shutdown_order.append("good"))

    def _raise(ctx):
        raise RuntimeError("boom")

    bad = _Plugin("bad", on_register=_raise, on_shutdown_cb=lambda ctx: shutdown_order.append("bad"))

    manager.load([good, bad])
    manager.shutdown()

    assert shutdown_order == ["good"]


def test_load_is_incremental_on_the_same_context():
    # Regression: a second load() used to forget the packages of the first
    # one, so they were never shut down (and could not be required).
    manager = PluginManager()
    shutdown_order = []
    base = _Plugin("base", on_shutdown_cb=lambda ctx: shutdown_order.append("base"))
    manager.load([base])

    later = _Plugin("later", requires=["base"], on_shutdown_cb=lambda ctx: shutdown_order.append("later"))
    report = manager.load([later])

    assert report.loaded == ["later"]
    assert manager.loaded_names == ["base", "later"]
    assert manager.report.loaded == ["base", "later"]
    manager.shutdown()
    assert shutdown_order == ["later", "base"]


def test_loading_an_already_loaded_package_fails_without_touching_it():
    manager = PluginManager()
    manager.load([_Plugin("a", on_register=_mark("a"))])

    report = manager.load([_Plugin("a")])

    assert [failure.plugin_name for failure in report.failed] == ["a"]
    assert manager.loaded_names == ["a"]


def test_unload_removes_contributions_and_publishes_package_unloaded():
    manager = PluginManager()
    shutdowns = []
    plugin = _Plugin(
        "a",
        on_register=_mark("a"),
        on_shutdown_cb=lambda ctx: shutdowns.append("a"),
    )
    manager.load([plugin])
    ctx = manager._ctx
    events = []
    ctx.event_bus.subscribe("package.unloaded", lambda payload: events.append(dict(payload)), owner="test")

    assert manager.unload("a") is plugin

    assert "a.a" not in ctx.importers
    assert manager.loaded_names == []
    assert shutdowns == ["a"]
    assert events == [{"package": "a", "version": "1.0.0"}]
    with pytest.raises(KeyError):
        manager.unload("a")
