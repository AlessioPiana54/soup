"""
------------------------------------------------------------------------
File : test_app_entrypoint.py
Description: The process entrypoint (app.py) turns on Flask's debug
             mode only when SOUP_DEBUG is "1" or "true" (any case).
Project : soup-server
------------------------------------------------------------------------
"""

import pytest

from app import debug_from_env


def test_debug_is_off_without_soup_debug():
    assert debug_from_env({}) is False


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "True", " true "])
def test_debug_is_on_with_1_or_true(value):
    assert debug_from_env({"SOUP_DEBUG": value}) is True


@pytest.mark.parametrize("value", ["", "0", "false", "yes", "on", "2"])
def test_any_other_value_leaves_debug_off(value):
    assert debug_from_env({"SOUP_DEBUG": value}) is False
