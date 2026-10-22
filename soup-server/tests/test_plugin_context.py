"""
------------------------------------------------------------------------
File : test_plugin_context.py
Description: Tests for DefaultPluginContext - contributions attributed to
             the current package, duplicate keys naming both packages,
             validation of contributions, and remove_owner() taking away
             everything one package contributed.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import pytest

from soup.core.contracts import PluginConflictError
from soup.core.plugin_context import DefaultPluginContext
from soup.core.plugin_manager import PluginManager
from tests.mediator_doubles import (
    FakeExporter,
    FakeImporter,
    FakeOperation,
    FakeTool,
    FakeVisualizer,
    FeaturePackage,
)

DATASET_INDEXED = "rich.dataset_indexed"


def _rich_package(name="rich", suffix=""):
    def _extra(ctx):
        ctx.add_extension_point(f"exporters{suffix}")
        ctx.contribute(f"exporters{suffix}", "item", key="k")
        ctx.subscribe(DATASET_INDEXED, lambda payload: None)

    return FeaturePackage(
        name,
        importers=[FakeImporter(f"imp{suffix}", "Imp")],
        operations=[FakeOperation(f"op{suffix}", inputs=[("t", ["table"])])],
        visualizers=[FakeVisualizer(f"vis{suffix}", ["table"])],
        exporters=[FakeExporter(f"exp{suffix}", ["table"])],
        tools=[FakeTool(f"tool{suffix}")],
        on_register=_extra,
    )


def test_contributions_are_attributed_to_their_package():
    ctx = DefaultPluginContext()
    PluginManager().load([_rich_package()], ctx=ctx)

    for registry, key in (
        (ctx.importers, "imp"), (ctx.operations, "op"), (ctx.visualizers, "vis"),
        (ctx.exporters, "exp"), (ctx.tool_registry, "tool"),
    ):
        assert registry.owner_of(key) == "rich"
    assert ctx.extension_points.owner_of("exporters") == "rich"


def test_remove_owner_removes_every_contribution_of_one_package():
    ctx = DefaultPluginContext()
    report = PluginManager().load([_rich_package("rich"), _rich_package("other", suffix="2")], ctx=ctx)
    assert report.failed == []

    ctx.remove_owner("rich")

    for registry in (ctx.importers, ctx.operations, ctx.visualizers, ctx.exporters, ctx.tool_registry):
        assert all(registry.owner_of(key) == "other" for key in registry.keys())
        assert len(registry) == 1
    assert ctx.extension_points.points() == ["exporters2"]
    assert [s.owner for s in ctx.event_bus.subscribers(DATASET_INDEXED)] == ["other"]


def test_duplicate_contribution_names_both_packages():
    ctx = DefaultPluginContext()
    first = FeaturePackage("first", visualizers=[FakeVisualizer("grid", ["table"])])
    second = FeaturePackage("second", visualizers=[FakeVisualizer("grid", ["event_log"])])

    report = PluginManager().load([first, second], ctx=ctx)

    error = report.failed[0].error
    assert isinstance(error, PluginConflictError)
    assert (error.existing_owner, error.new_owner, error.key) == ("first", "second", "grid")


@pytest.mark.parametrize(
    "package",
    [
        FeaturePackage("p", importers=[FakeImporter("imp", "Imp", produces="")]),
        FeaturePackage("p", operations=[FakeOperation("op", inputs=[])]),
        FeaturePackage("p", operations=[FakeOperation("op", inputs=[("a", ["t"]), ("a", ["t"])])]),
        FeaturePackage("p", operations=[FakeOperation("op", inputs=[("a", ["t"])], produces=())]),
        FeaturePackage("p", visualizers=[FakeVisualizer("vis", [])]),
        FeaturePackage("p", exporters=[FakeExporter("exp", ["table"], extension="csv")]),
    ],
)
def test_invalid_contributions_are_refused(package):
    ctx = DefaultPluginContext()

    report = PluginManager().load([package], ctx=ctx)

    assert report.loaded == []
    assert isinstance(report.failed[0].error, ValueError)


def test_visualizer_element_must_be_a_custom_element_tag():
    visualizer = FakeVisualizer("grid", ["table"])
    visualizer.element = "grid"

    report = PluginManager().load([FeaturePackage("p", visualizers=[visualizer])], ctx=DefaultPluginContext())

    assert "custom-element" in report.failed[0].reason
