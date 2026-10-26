"""
------------------------------------------------------------------------
File : test_package_contributions.py
Description: Tests for the names packages contribute under: importers
             (and operations, visualizers, exporters) are scoped to their
             package ("<package>.<id>"), so two packages may both offer
             an importer "csv"; tools and extension points keep a global
             name, must be declared in the manifest, and two active
             packages cannot declare the same one (checked before any
             code is imported, both packages named in the conflict).
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import io
import sys

import pytest

from soup.core.contracts import (
    ConflictError,
    ExtensionPointNotDeclaredError,
    PluginConflictError,
    ToolNotDeclaredError,
)
from soup.core.engine import build_engine
from soup.core.settings import Settings
from tests.fakes import CoreToolsPackage
from tests.mediator_doubles import upload
from tests.package_builder import (
    EXPLODING_INIT,
    IMPORTER_PLUGIN,
    UNDECLARED_POINT_PLUGIN,
    UNDECLARED_TOOL_PLUGIN,
    build_zip,
    write_package,
)


@pytest.fixture(autouse=True)
def _forget_test_modules():
    before = set(sys.modules)
    yield
    for name in set(sys.modules) - before:
        if name.startswith("soup_pkg_"):
            del sys.modules[name]


@pytest.fixture
def dirs(tmp_path):
    bundled, installed = tmp_path / "bundled", tmp_path / "installed"
    bundled.mkdir()
    return bundled, installed


def _engine(bundled, installed, extra=()):
    settings = Settings(
        packages_path=(str(bundled), str(installed)), installed_packages_dir=str(installed), allow_package_install=True
    )
    return build_engine(settings, extra_plugins=extra)


def _failure(report, name):
    return next(failure.error for failure in report.failed if failure.plugin_name == name)


def test_two_packages_with_an_importer_csv_both_load_and_are_both_offered(dirs):
    bundled, _ = dirs
    write_package(bundled, "alpha", plugin_source=IMPORTER_PLUGIN)
    write_package(bundled, "beta", plugin_source=IMPORTER_PLUGIN)
    engine = _engine(*dirs, extra=[CoreToolsPackage()])

    assert {"alpha", "beta"} <= set(engine.report.loaded)
    router = engine.import_router
    offered = router.importers_for("orders.csv")
    assert [entry.key for entry in offered] == ["alpha.csv", "beta.csv"]
    assert [entry.package for entry in offered] == ["alpha", "beta"]
    assert [entry.item.id for entry in offered] == ["csv", "csv"]
    assert router.package_of("beta.csv") == "beta"

    obj = router.import_("beta.csv", upload(), "orders")
    assert obj.created_by.to_dict() == {"type": "importer", "contributor_id": "beta.csv", "package": "beta"}


def test_disabling_one_package_keeps_the_other_importer(dirs):
    bundled, _ = dirs
    write_package(bundled, "alpha", plugin_source=IMPORTER_PLUGIN)
    write_package(bundled, "beta", plugin_source=IMPORTER_PLUGIN)
    engine = _engine(*dirs)

    engine.package_manager.disable("alpha")

    assert [entry.key for entry in engine.import_router.importers_for("x.csv")] == ["beta.csv"]


def test_tool_not_declared_in_the_manifest_is_refused(dirs):
    bundled, _ = dirs
    write_package(bundled, "alpha", plugin_source=UNDECLARED_TOOL_PLUGIN)
    engine = _engine(*dirs)

    error = _failure(engine.report, "alpha")
    assert isinstance(error, ToolNotDeclaredError)
    assert "provides_tools" in str(error)
    assert "secret" not in engine.ctx.tool_registry


def test_extension_point_not_declared_in_the_manifest_is_refused(dirs):
    bundled, _ = dirs
    write_package(bundled, "alpha", plugin_source=UNDECLARED_POINT_PLUGIN)
    engine = _engine(*dirs)

    assert isinstance(_failure(engine.report, "alpha"), ExtensionPointNotDeclaredError)
    assert engine.ctx.extension_points.points() == []


def test_declared_extension_point_is_opened(dirs):
    bundled, _ = dirs
    write_package(bundled, "alpha", extension_points=["ekg.build_steps"])
    engine = _engine(*dirs)

    assert engine.ctx.extension_points.owner_of("ekg.build_steps") == "alpha"
    assert engine.package_manager.info("alpha").extension_points == ("ekg.build_steps",)


@pytest.mark.parametrize(
    ("field", "kind"), [("provides_tools", "tool"), ("extension_points", "extension_point")]
)
def test_same_global_name_in_two_packages_is_a_conflict_found_before_import(dirs, field, kind):
    bundled, _ = dirs
    write_package(bundled, "alpha", **{field: ["memgraph"]})
    write_package(bundled, "beta", init_source=EXPLODING_INIT, **{field: ["memgraph"]})
    engine = _engine(*dirs)

    assert "alpha" in engine.report.loaded
    error = _failure(engine.report, "beta")
    assert isinstance(error, PluginConflictError)
    assert (error.kind, error.key, error.existing_owner, error.new_owner) == (kind, "memgraph", "alpha", "beta")
    assert "'alpha'" in str(error) and "'beta'" in str(error)
    assert "soup_pkg_beta" not in sys.modules


def test_a_disabled_package_does_not_hold_its_global_names(dirs):
    bundled, _ = dirs
    write_package(bundled, "alpha", provides_tools=["memgraph"])
    write_package(bundled, "beta", provides_tools=["memgraph"])
    engine = _engine(*dirs)
    packages = engine.package_manager

    with pytest.raises(ConflictError) as error:
        packages.enable("beta")
    assert error.value.details == {"conflict": {"kind": "tool", "name": "memgraph", "packages": ["alpha", "beta"]}}

    packages.disable("alpha")
    assert packages.enable("beta").status == "active"
    assert engine.ctx.tool_registry.owner_of("memgraph") == "beta"


def test_install_of_a_package_declaring_a_taken_name_is_409(tmp_path, dirs):
    bundled, installed = dirs
    write_package(bundled, "alpha", extension_points=["ekg.build_steps"])
    engine = _engine(*dirs)

    with pytest.raises(ConflictError) as error:
        engine.package_manager.install(io.BytesIO(build_zip(tmp_path, "beta", extension_points=["ekg.build_steps"])))

    assert error.value.details["conflict"]["packages"] == ["alpha", "beta"]
    assert not (installed / "beta").exists()
