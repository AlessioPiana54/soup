"""
------------------------------------------------------------------------
File : test_plugin_tools.py
Description: Tests for tools in the package lifecycle: a package whose
             required tools are missing is dropped (with the reason in
             the PluginReport, or an error in strict mode), providers
             load before consumers, a package failing half-way is rolled
             back, ToolBox refuses tools that were not declared, and the
             engine reports missing core tools (catalog, preferences).
             Also checks the package.loaded/unloaded events.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import pytest

from soup.core.contracts import (
    PluginError,
    PluginMissingToolsError,
    ServiceUnavailableError,
    ToolNotDeclaredError,
)
from soup.core.events import PACKAGE_LOADED, PACKAGE_UNLOADED
from soup.core.plugin_context import DefaultPluginContext
from soup.core.plugin_manager import PluginManager
from tests.fakes import LegacyToolsPackage
from tests.mediator_doubles import FakeImporter, FakeOperation, FakeTool, FeaturePackage, build_test_engine, upload


def _failures(report):
    return {failure.plugin_name: failure for failure in report.failed}


def test_package_requiring_a_missing_tool_is_dropped_with_the_reason():
    ctx = DefaultPluginContext()
    consumer = FeaturePackage("consumer", requires_tools=("graph",), importers=[FakeImporter("imp", "Imp")])
    other = FeaturePackage("other", operations=[FakeOperation("op", inputs=[("t", ["table"])])])

    report = PluginManager().load([consumer, other], ctx=ctx)

    assert report.loaded == ["other"]
    failure = _failures(report)["consumer"]
    assert isinstance(failure.error, PluginMissingToolsError)
    assert failure.error.missing == ["graph"]
    assert "graph" in failure.reason
    assert "imp" not in ctx.importers


def test_strict_mode_raises_on_a_missing_tool():
    with pytest.raises(PluginMissingToolsError):
        PluginManager(strict=True).load([FeaturePackage("consumer", requires_tools=("graph",))])


def test_tool_providers_load_before_their_consumers():
    order = []
    consumer = FeaturePackage("consumer", requires_tools=("graph",), on_register=lambda ctx: order.append("consumer"))
    provider = FeaturePackage("provider", tools=[FakeTool("graph")], on_register=lambda ctx: order.append("provider"))

    report = PluginManager().load([consumer, provider], ctx=DefaultPluginContext())

    assert order == ["provider", "consumer"]
    assert report.loaded == ["provider", "consumer"]


def test_consumer_is_dropped_when_its_provider_fails_verification():
    provider = FeaturePackage("provider", tools=[FakeTool("graph")])
    provider.api_version = "1.0"
    consumer = FeaturePackage("consumer", requires_tools=("graph",))

    report = PluginManager().load([provider, consumer], ctx=DefaultPluginContext())

    assert report.loaded == []
    assert isinstance(_failures(report)["consumer"].error, PluginMissingToolsError)


def test_consumer_is_dropped_when_its_provider_fails_to_register_and_the_provider_is_rolled_back():
    def _explode(ctx):
        raise RuntimeError("boom")

    ctx = DefaultPluginContext()
    provider = FeaturePackage(
        "provider", tools=[FakeTool("graph")], importers=[FakeImporter("half", "Half")], on_register=_explode
    )
    consumer = FeaturePackage("consumer", requires_tools=("graph",))

    report = PluginManager().load([provider, consumer], ctx=ctx)

    assert report.loaded == []
    assert isinstance(_failures(report)["consumer"].error, PluginMissingToolsError)
    assert "graph" not in ctx.tool_registry
    assert "half" not in ctx.importers


def test_contributions_may_only_require_tools_the_package_declared():
    sneaky = FeaturePackage("sneaky", importers=[FakeImporter("imp", "Imp", requires_tools=("graph",))])
    provider = FeaturePackage("provider", tools=[FakeTool("graph")])

    report = PluginManager().load([provider, sneaky], ctx=DefaultPluginContext())

    assert report.loaded == ["provider"]
    assert isinstance(_failures(report)["sneaky"].error, ToolNotDeclaredError)


def test_tools_must_be_declared_in_provides_tools_and_actually_added():
    undeclared = FeaturePackage("undeclared", tools=[FakeTool("graph")], provides_tools=())
    lazy = FeaturePackage("lazy", provides_tools=("storage",))

    report = PluginManager().load([undeclared, lazy], ctx=DefaultPluginContext())

    failures = _failures(report)
    assert isinstance(failures["undeclared"].error, ToolNotDeclaredError)
    assert failures["undeclared"].error.declaration == "provides_tools"
    assert isinstance(failures["lazy"].error, PluginError)
    assert "did not add" in failures["lazy"].reason


def test_toolbox_refuses_a_loaded_tool_that_was_not_declared():
    seen = {}

    def _use_tools(ctx):
        seen["graph"] = ctx.tools.get("graph")
        seen["has_storage"] = ctx.tools.has("storage")
        with pytest.raises(ToolNotDeclaredError):
            ctx.tools.get("storage")

    graph = FakeTool("graph")
    provider = FeaturePackage("provider", tools=[graph, FakeTool("storage")])
    consumer = FeaturePackage("consumer", requires_tools=("graph",), on_register=_use_tools)

    report = PluginManager().load([provider, consumer], ctx=DefaultPluginContext())

    assert report.failed == []
    assert seen == {"graph": graph, "has_storage": False}


def test_contribution_toolbox_only_exposes_its_own_tools():
    seen = {}

    class _ToolUsingImporter(FakeImporter):
        def import_(self, upload, obj, options, tools):
            seen["graph"] = tools.get("graph").name
            with pytest.raises(ToolNotDeclaredError):
                tools.get("storage")
            return {}

    package = FeaturePackage(
        "feature",
        tools=[FakeTool("graph"), FakeTool("storage")],
        importers=[_ToolUsingImporter("imp", "Imp", requires_tools=("graph",))],
    )
    engine, _core = build_test_engine(package)

    engine.import_router.import_("feature.imp", upload(), "ds")

    assert seen == {"graph": "graph"}


def test_engine_reports_missing_core_tools_and_still_starts():
    engine, _core = build_test_engine(with_core_tools=False)

    assert any("'catalog'" in warning for warning in engine.report.warnings)
    assert any("'preferences'" in warning for warning in engine.report.warnings)
    with pytest.raises(ServiceUnavailableError, match="catalog"):
        engine.core_tools.catalog()
    with pytest.raises(ServiceUnavailableError, match="preferences"):
        engine.core_tools.preferences()


def test_engine_with_every_tool_has_no_warnings():
    engine, core = build_test_engine(LegacyToolsPackage())

    assert engine.report.warnings == []
    engine.core_tools.preferences().set("theme", "dark")
    assert core.preferences.get("theme") == "dark"


def test_core_tool_of_the_wrong_type_is_reported():
    engine, _core = build_test_engine(FeaturePackage("impostor", tools=[FakeTool("catalog")]), with_core_tools=False)

    assert any("not a Catalog" in warning for warning in engine.report.warnings)
    with pytest.raises(ServiceUnavailableError, match="not a Catalog"):
        engine.workspace_service.list()


def test_package_loaded_and_unloaded_events():
    events = []
    listener = FeaturePackage(
        "listener",
        on_register=lambda ctx: (
            ctx.subscribe(PACKAGE_LOADED, lambda p: events.append(("loaded", p["package"]))),
            ctx.subscribe(PACKAGE_UNLOADED, lambda p: events.append(("unloaded", p["package"]))),
        ),
    )
    manager = PluginManager()
    manager.load([listener, FeaturePackage("other", requires=("listener",))], ctx=DefaultPluginContext())
    manager.shutdown()

    assert events == [("loaded", "listener"), ("loaded", "other"), ("unloaded", "other"), ("unloaded", "listener")]
