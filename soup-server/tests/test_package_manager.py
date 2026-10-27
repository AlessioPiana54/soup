"""
------------------------------------------------------------------------
File : test_package_manager.py
Description: Tests for PackageManager.load_all (soup.core.packages):
             discovery from several folders, ordering on `requires`,
             cycles, api_version and Python dependency checks made
             before any code is imported, isolated module names, the
             SOUP_PACKAGES override and the persisted state.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import sys

import pytest

from soup.core.contracts import (
    PluginApiVersionError,
    PluginCycleError,
    PluginDependencyError,
    PluginPythonDependencyError,
)
from soup.core.event_bus import EventBus
from soup.core.packages import PackageManager, PackageManagerConfig
from soup.core.plugin_context import DefaultPluginContext
from soup.core.plugin_manager import PluginManager
from tests.package_builder import EXPLODING_INIT, markers, write_package


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
    installed.mkdir()
    return bundled, installed


def _manager(bundled, installed, version_lookup=None, **config):
    ctx = DefaultPluginContext(EventBus())
    kwargs = {"version_lookup": version_lookup} if version_lookup else {}
    manager = PackageManager(
        PluginManager(),
        ctx,
        PackageManagerConfig(packages_path=(str(bundled), str(installed)), installed_dir=str(installed), **config),
        **kwargs,
    )
    return manager, ctx


def _failure(report, name):
    return next(failure for failure in report.failed if failure.plugin_name == name)


def test_discovery_from_two_folders(dirs):
    bundled, installed = dirs
    write_package(bundled, "alpha")
    write_package(installed, "beta")

    manager, ctx = _manager(bundled, installed)
    report = manager.load_all()

    assert sorted(report.loaded) == ["alpha", "beta"]
    assert {info.name: info.origin for info in manager.list()} == {"alpha": "bundled", "beta": "installed"}
    assert {"alpha", "beta"} <= markers(ctx)


def test_same_name_in_two_folders_keeps_the_higher_version(dirs):
    bundled, installed = dirs
    write_package(bundled, "alpha", version="1.0.0", marker="old")
    write_package(installed, "alpha", version="1.2.0", marker="new")

    manager, ctx = _manager(bundled, installed)
    report = manager.load_all()

    assert manager.info("alpha").version == "1.2.0"
    assert "new" in markers(ctx) and "old" not in markers(ctx)
    assert any("found twice" in warning for warning in report.warnings)


def test_folders_starting_with_underscore_or_dot_are_skipped(dirs):
    bundled, installed = dirs
    write_package(installed, "_staging")
    write_package(installed, ".hidden")

    manager, _ = _manager(bundled, installed)

    assert manager.load_all().loaded == []


def test_requires_orders_loading(dirs):
    bundled, installed = dirs
    write_package(bundled, "alpha", requires=["beta"])
    write_package(bundled, "beta")

    manager, _ = _manager(bundled, installed)

    assert manager.load_all().loaded == ["beta", "alpha"]


def test_cycle_is_isolated_in_the_report(dirs):
    bundled, installed = dirs
    write_package(bundled, "alpha", requires=["beta"])
    write_package(bundled, "beta", requires=["alpha"])
    write_package(bundled, "gamma")

    manager, _ = _manager(bundled, installed)
    report = manager.load_all()

    assert report.loaded == ["gamma"]
    assert isinstance(_failure(report, "alpha").error, PluginCycleError)
    assert isinstance(_failure(report, "beta").error, PluginCycleError)
    assert manager.info("alpha").status == "failed"


def test_cycle_raises_in_strict_mode(dirs):
    bundled, installed = dirs
    write_package(bundled, "alpha", requires=["beta"])
    write_package(bundled, "beta", requires=["alpha"])

    manager, _ = _manager(bundled, installed, strict=True)

    with pytest.raises(PluginCycleError):
        manager.load_all()


def test_missing_required_package_fails_with_its_dependents(dirs):
    bundled, installed = dirs
    write_package(bundled, "alpha", requires=["nowhere"])
    write_package(bundled, "beta", requires=["alpha"])

    manager, _ = _manager(bundled, installed)
    report = manager.load_all()

    assert report.loaded == []
    assert isinstance(_failure(report, "alpha").error, PluginDependencyError)
    assert isinstance(_failure(report, "beta").error, PluginDependencyError)


def test_incompatible_api_version_is_reported_without_importing_code(dirs):
    bundled, installed = dirs
    write_package(bundled, "alpha", api_version="1.0", init_source=EXPLODING_INIT)

    manager, _ = _manager(bundled, installed)
    report = manager.load_all()

    assert report.loaded == []
    assert isinstance(_failure(report, "alpha").error, PluginApiVersionError)
    assert "soup_pkg_alpha" not in sys.modules


def test_missing_python_dependency_is_reported_without_importing_code(dirs):
    bundled, installed = dirs
    write_package(
        bundled, "alpha", python_dependencies=["surely-not-installed-lib>=1"], init_source=EXPLODING_INIT
    )
    write_package(bundled, "beta", python_dependencies=["pytest<1"], init_source=EXPLODING_INIT)
    write_package(bundled, "gamma", python_dependencies=["pytest>=7"])

    manager, _ = _manager(bundled, installed)
    report = manager.load_all()

    assert report.loaded == ["gamma"]
    alpha = _failure(report, "alpha").error
    assert isinstance(alpha, PluginPythonDependencyError)
    assert "'surely-not-installed-lib>=1' (not installed)" in str(alpha)
    assert "not installed at runtime" in str(alpha)
    assert "installed:" in str(_failure(report, "beta").error)
    assert manager.info("alpha").error == str(alpha)


def test_a_failing_import_is_isolated(dirs):
    bundled, installed = dirs
    write_package(bundled, "alpha", init_source=EXPLODING_INIT)
    write_package(bundled, "beta", requires=["alpha"])
    write_package(bundled, "gamma")

    manager, _ = _manager(bundled, installed)
    report = manager.load_all()

    assert report.loaded == ["gamma"]
    assert "must not be imported" in _failure(report, "alpha").reason
    assert isinstance(_failure(report, "beta").error, PluginDependencyError)


def test_server_modules_are_imported_under_isolated_names(dirs):
    bundled, installed = dirs
    # Same file names (server/helper.py, server/plugin.py) in both packages.
    write_package(bundled, "alpha", marker="from-alpha")
    write_package(bundled, "beta", marker="from-beta")

    manager, ctx = _manager(bundled, installed)
    manager.load_all()

    assert {"from-alpha", "from-beta"} <= markers(ctx)
    assert sys.modules["soup_pkg_alpha.helper"].MARKER == "from-alpha"
    assert sys.modules["soup_pkg_beta.helper"].MARKER == "from-beta"


def test_manifest_identity_is_set_on_the_plugin(dirs):
    bundled, installed = dirs
    write_package(bundled, "alpha", version="3.1.4", provides_tools=["thing"])

    manager, ctx = _manager(bundled, installed)
    manager.load_all()

    plugin = manager.plugin_manager.get("alpha")
    assert (plugin.name, plugin.version, tuple(plugin.provides_tools)) == ("alpha", "3.1.4", ("thing",))
    assert ctx.tool_registry.owner_of("thing") == "alpha"


def test_soup_packages_override_selects_the_active_packages(dirs):
    bundled, installed = dirs
    write_package(bundled, "alpha")
    write_package(bundled, "beta")

    manager, _ = _manager(bundled, installed, enabled_override=("alpha", "ghost"))
    report = manager.load_all()

    assert report.loaded == ["alpha"]
    assert report.disabled == ["beta"]
    assert any("'ghost'" in warning for warning in report.warnings)


def test_disabled_state_is_persisted_across_restarts(dirs):
    bundled, installed = dirs
    write_package(bundled, "alpha")
    write_package(bundled, "beta")
    first, _ = _manager(bundled, installed)
    first.load_all()

    first.disable("beta")

    second, _ = _manager(bundled, installed)
    report = second.load_all()
    assert report.loaded == ["alpha"]
    assert report.disabled == ["beta"]
    assert (installed / "_state.json").is_file()


def test_invalid_manifest_on_disk_is_reported_not_raised(dirs):
    bundled, installed = dirs
    write_package(bundled, "alpha")
    broken = bundled / "broken"
    broken.mkdir()
    (broken / "soup-package.json").write_text("{}", encoding="utf-8")

    manager, _ = _manager(bundled, installed)
    report = manager.load_all()

    assert report.loaded == ["alpha"]
    assert _failure(report, "broken").error.http_status_code == 400
