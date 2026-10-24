"""
------------------------------------------------------------------------
File : test_api_version.py
Description: Tests for the contracts version rule
             (soup.core.contracts.version): same major as the host, minor
             not above the host's - applied by the PluginManager and by
             the PackageManager (before importing any code).
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import sys

import pytest

from soup.core.contracts import PluginApiVersionError, is_api_compatible, parse_api_version
from soup.core.event_bus import EventBus
from soup.core.packages import PackageManager, PackageManagerConfig
from soup.core.plugin_context import DefaultPluginContext
from soup.core.plugin_manager import PluginManager
from tests.mediator_doubles import FeaturePackage
from tests.package_builder import write_package

HOST = "2.1"
COMPATIBLE = ["2.0", "2.1"]
INCOMPATIBLE = ["1.0", "1.9", "3.0", "2.2"]


@pytest.mark.parametrize("version", COMPATIBLE)
def test_same_major_and_lower_or_equal_minor_is_compatible(version):
    assert is_api_compatible(version, HOST)


@pytest.mark.parametrize("version", [*INCOMPATIBLE, "2", "2.1.0", "v2.1", "", None, 2.1])
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

    assert sorted(report.loaded) == ["v2_0", "v2_1"]
    failed = {failure.plugin_name: failure.error for failure in report.failed}
    assert sorted(failed) == sorted(["v1_0", "v1_9", "v3_0", "v2_2"])
    assert all(isinstance(error, PluginApiVersionError) for error in failed.values())
    assert "same major" in str(failed["v2_2"])
