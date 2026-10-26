"""
------------------------------------------------------------------------
File : test_settings_defaults.py
Description: Tests that Settings.from_env() activates every package
             found by default - so the bundled packages (csv_reader,
             causal_df, tool_memgraph, tool_storage) load, with no I/O
             until a tool is used, and causal_df's build step actually ends up
             in the pipeline (regression test for the bug where
             trigger/target pairs were silently ignored in production
             because causal_df was never loaded) - and the package
             settings read from the environment.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import os

from soup.core.engine import build_engine
from soup.core.settings import (
    DEFAULT_BUNDLED_PACKAGES_DIR,
    DEFAULT_INSTALLED_PACKAGES_DIR,
    Settings,
)


def test_default_settings_activate_every_package_found():
    settings = Settings.from_env({})
    assert settings.packages is None
    assert settings.packages_path == (DEFAULT_BUNDLED_PACKAGES_DIR, DEFAULT_INSTALLED_PACKAGES_DIR)
    assert settings.allow_package_install is False


BUNDLED = ["causal_df", "csv_reader", "tool_memgraph", "tool_storage"]


def test_from_env_with_no_overrides_loads_every_bundled_package():
    engine = build_engine(Settings.from_env({}))

    assert engine.report.failed == []
    assert set(BUNDLED) <= set(engine.report.loaded)
    # Every tool the core relies on is provided by a bundled package.
    assert engine.report.warnings == []
    assert sorted(engine.ctx.tool_registry.keys()) == ["catalog", "memgraph", "preferences", "storage"]


def test_causal_step_is_in_the_pipeline_by_default():
    engine = build_engine(Settings.from_env({}))

    pipeline = engine.ekg_service.build_pipeline()

    assert [step.order for step in pipeline] == [100, 200, 300, 400, 450, 500]
    assert "causal_directly_follows" in [step.key for step in pipeline]


def test_explicit_empty_soup_packages_disables_everything():
    # SOUP_PACKAGES="" is the documented way to opt out of every package,
    # distinct from the variable being entirely absent.
    settings = Settings.from_env({"SOUP_PACKAGES": ""})
    assert settings.packages == ()

    engine = build_engine(settings)
    assert engine.report.loaded == []
    assert sorted(engine.report.disabled) == BUNDLED


def test_soup_plugins_is_still_read_as_an_alias_of_soup_packages():
    assert Settings.from_env({"SOUP_PLUGINS": "csv_reader"}).packages == ("csv_reader",)
    assert Settings.from_env({"SOUP_PACKAGES": "causal_df", "SOUP_PLUGINS": "csv_reader"}).packages == ("causal_df",)


def test_package_settings_from_env(tmp_path):
    first, second, installed = tmp_path / "a", tmp_path / "b", tmp_path / "installed"
    settings = Settings.from_env({
        "SOUP_PACKAGES_PATH": os.pathsep.join([str(first), str(second)]),
        "SOUP_INSTALLED_PACKAGES_DIR": str(installed),
        "SOUP_ALLOW_PACKAGE_INSTALL": "true",
    })

    # The installed-packages folder is always searched, so installed
    # packages are found again at the next start.
    assert settings.packages_path == (str(first), str(second), str(installed))
    assert settings.installed_packages_dir == str(installed)
    assert settings.allow_package_install is True
