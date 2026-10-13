"""
------------------------------------------------------------------------
File : test_settings_defaults.py
Description: Tests that Settings.from_env() defaults to BOTH built-in
             plugins (csv_reader and causal_df) and that causal_df's
             build step actually ends up in the pipeline - regression
             test for the bug where trigger/target pairs were silently
             ignored in production because causal_df was never loaded.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from soup.core.engine import build_engine
from soup.core.settings import Settings
from tests.fakes import FakeDatabase, InMemoryFileStorage


def test_default_plugins_include_csv_reader_and_causal_df():
    settings = Settings.from_env({})
    assert settings.plugins == ("csv_reader", "causal_df")


def test_from_env_with_no_overrides_loads_both_built_in_plugins():
    engine = build_engine(Settings.from_env({}), db=FakeDatabase(), storage=InMemoryFileStorage())

    assert engine.report.failed == []
    assert "csv_reader" in engine.report.loaded
    assert "causal_df" in engine.report.loaded


def test_causal_step_is_in_the_pipeline_by_default():
    engine = build_engine(Settings.from_env({}), db=FakeDatabase(), storage=InMemoryFileStorage())

    pipeline = engine.ekg_service.build_pipeline()

    assert [step.order for step in pipeline] == [100, 200, 300, 400, 450, 500]
    assert "causal_directly_follows" in [step.key for step in pipeline]


def test_explicit_empty_soup_plugins_still_disables_everything():
    # SOUP_PLUGINS="" is the documented way to opt out of every plugin,
    # distinct from the variable being entirely absent.
    settings = Settings.from_env({"SOUP_PLUGINS": ""})
    assert settings.plugins == ()
