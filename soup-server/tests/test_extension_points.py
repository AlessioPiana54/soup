"""
------------------------------------------------------------------------
File : test_extension_points.py
Description: Tests for add_extension_point / contribute / contributions:
             ordering, duplicate keys and points, unknown points, and
             rollback of a failing contributor.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import pytest

from soup.core.contracts import ExtensionPointError, PluginConflictError
from soup.core.plugin_context import DefaultPluginContext
from soup.core.plugin_manager import PluginManager
from tests.mediator_doubles import FeaturePackage

POINT = "exporters"


def _owner():
    return FeaturePackage("owner", on_register=lambda ctx: ctx.add_extension_point(POINT))


def _contributor(name, *contributions, fail=False):
    def _register(ctx):
        for key, item, order in contributions:
            ctx.contribute(POINT, item, key=key, order=order)
        if fail:
            raise RuntimeError("boom")

    return FeaturePackage(name, requires=("owner",), on_register=_register)


def _failures(report):
    return {failure.plugin_name: failure.error for failure in report.failed}


def test_contributions_are_ordered_by_order_then_registration():
    ctx = DefaultPluginContext()
    report = PluginManager().load(
        [
            _contributor("a", ("csv", "CSV", 20), ("json", "JSON", 10)),
            _contributor("b", ("xes", "XES", 10), ("svg", "SVG", 0)),
            _owner(),
        ],
        ctx=ctx,
    )

    assert report.failed == []
    assert ctx.contributions(POINT) == ["SVG", "JSON", "XES", "CSV"]


def test_duplicate_contribution_key_isolates_the_second_package():
    ctx = DefaultPluginContext()
    report = PluginManager().load(
        [_owner(), _contributor("a", ("csv", "A", 0)), _contributor("b", ("pdf", "B-pdf", 0), ("csv", "B", 0))],
        ctx=ctx,
    )

    error = _failures(report)["b"]
    assert isinstance(error, PluginConflictError)
    assert (error.existing_owner, error.new_owner, error.key) == ("a", "b", "csv")
    assert ctx.contributions(POINT) == ["A"]  # b's earlier contribution was rolled back too


def test_duplicate_extension_point_is_a_conflict():
    other_owner = FeaturePackage("other", on_register=lambda c: c.add_extension_point(POINT))

    report = PluginManager().load([_owner(), other_owner], ctx=DefaultPluginContext())

    assert isinstance(_failures(report)["other"], PluginConflictError)


def test_unknown_point_is_an_error():
    ctx = DefaultPluginContext()
    lonely = FeaturePackage("lonely", on_register=lambda c: c.contribute("nowhere", object(), key="k"))

    report = PluginManager().load([lonely], ctx=ctx)

    assert isinstance(_failures(report)["lonely"], ExtensionPointError)
    with pytest.raises(ExtensionPointError):
        ctx.contributions("nowhere")


def test_failing_contributor_leaves_no_contribution_behind():
    ctx = DefaultPluginContext()
    report = PluginManager().load([_owner(), _contributor("bad", ("csv", "CSV", 0), fail=True)], ctx=ctx)

    assert "bad" in _failures(report)
    assert ctx.contributions(POINT) == []
