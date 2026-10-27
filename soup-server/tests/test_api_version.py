"""
------------------------------------------------------------------------
File : test_api_version.py
Description: Tests for the contracts version rule
             (soup.core.contracts.version): same major as the host, minor
             not above the host's - applied by the PluginManager and by
             the PackageManager (before importing any code); the host is
             at "3.0" since commit 8, so a "2.0" manifest is refused, and
             every bundled package declares "3.0".
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import sys

import pytest

from soup.core.contracts import CONTRACTS_API_VERSION, PluginApiVersionError, is_api_compatible, parse_api_version
from soup.core.event_bus import EventBus
from soup.core.packages import PackageManager, PackageManagerConfig
from soup.core.plugin_context import DefaultPluginContext
from soup.core.plugin_manager import PluginManager
from tests.mediator_doubles import FeaturePackage
from tests.package_builder import write_package

HOST = "3.1"
COMPATIBLE = ["3.0", "3.1"]
INCOMPATIBLE = ["2.0", "2.1", "4.0", "3.2"]


@pytest.mark.parametrize("version", COMPATIBLE)
def test_same_major_and_lower_or_equal_minor_is_compatible(version):
    assert is_api_compatible(version, HOST)


@pytest.mark.parametrize("version", [*INCOMPATIBLE, "3", "3.1.0", "v3.1", "", None, 3.1])
def test_other_majors_higher_minors_and_malformed_versions_are_not(version):
    assert not is_api_compatible(version, HOST)


def test_parse_api_version():
    assert parse_api_version("2.10") == (2, 10)
    assert parse_api_version("02.1") is None


def test_plugin_manager_applies_the_rule():
    plugins = [FeaturePackage(f"p{index}") for index in range(len(COMPATIBLE + INCOMPATIBLE))]
    for plugin, version in zip(plugins, COMPATIBLE + INCOMPATIBLE, strict=True):
        plugin.api_version = version

    report = PluginManager(contracts_api_version=HOST).load(plugins, ctx=DefaultPluginContext())

    assert report.loaded == ["p0", "p1"]
    assert all(isinstance(failure.error, PluginApiVersionError) for failure in report.failed)
    assert len(report.failed) == len(INCOMPATIBLE)


def test_package_manager_applies_the_rule(tmp_path):
    before = set(sys.modules)
    names = {f"v{version.replace('.', '_')}": version for version in COMPATIBLE + INCOMPATIBLE}
    for name, version in names.items():
        write_package(tmp_path, name, api_version=version)
    manager = PackageManager(
        PluginManager(contracts_api_version=HOST),
        DefaultPluginContext(EventBus()),
        PackageManagerConfig(
            packages_path=(str(tmp_path),), installed_dir=str(tmp_path / "_installed"), contracts_api_version=HOST
        ),
    )

    try:
        report = manager.load_all()
    finally:
        for module in set(sys.modules) - before:
            if module.startswith("soup_pkg_"):
                del sys.modules[module]

    assert sorted(report.loaded) == ["v3_0", "v3_1"]
    failed = {failure.plugin_name: failure.error for failure in report.failed}
    assert sorted(failed) == sorted(["v2_0", "v2_1", "v4_0", "v3_2"])
    assert all(isinstance(error, PluginApiVersionError) for error in failed.values())
    assert "same major" in str(failed["v3_2"])


def _load_on_the_real_host(tmp_path, versions):
    before = set(sys.modules)
    for name, version in versions.items():
        write_package(tmp_path, name, api_version=version)
    manager = PackageManager(
        PluginManager(),
        DefaultPluginContext(EventBus()),
        PackageManagerConfig(packages_path=(str(tmp_path),), installed_dir=str(tmp_path / "_installed")),
    )
    try:
        return manager.load_all()
    finally:
        for module in set(sys.modules) - before:
            if module.startswith("soup_pkg_"):
                del sys.modules[module]


def test_the_host_is_at_3_0_and_refuses_a_2_0_manifest(tmp_path):
    assert CONTRACTS_API_VERSION == "3.0"

    report = _load_on_the_real_host(tmp_path, {"old": "2.0", "current": "3.0"})

    assert report.loaded == ["current"]
    [failure] = report.failed
    assert failure.plugin_name == "old"
    assert isinstance(failure.error, PluginApiVersionError)
    message = str(failure.error)
    assert "'2.0'" in message and "'3.0'" in message and "same major" in message


def test_a_3_1_manifest_needs_a_3_1_host(tmp_path):
    # Minor releases only add: a "3.1" package loads on a "3.1" host (see
    # test_package_manager_applies_the_rule), not on the current "3.0".
    assert is_api_compatible("3.1", "3.1")
    assert not is_api_compatible("3.1")


def test_every_bundled_manifest_declares_the_host_version():
    import json

    from tests.packages import BUNDLED_PACKAGES_DIR

    manifests = sorted(BUNDLED_PACKAGES_DIR.glob("*/soup-package.json"))
    assert len(manifests) >= 9
    for path in manifests:
        assert json.loads(path.read_text(encoding="utf-8"))["api_version"] == CONTRACTS_API_VERSION, path
