"""
------------------------------------------------------------------------
File : test_process_timer.py
Description: Tests for ProcessTimer (ekg package, process_timer.py;
             moved from soup-server/tests).
Project : soup-packages/ekg
------------------------------------------------------------------------
"""

from datetime import datetime

import pytest

from tests.packages import bundled_module

_timer = bundled_module("ekg", "process_timer")
DATE_FORMAT, ProcessTimer = _timer.DATE_FORMAT, _timer.ProcessTimer


def test_date_format_matches_the_legacy_config_format():
    # Services/generic_graph_service.py:
    #   datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3]
    assert DATE_FORMAT == "%Y-%m-%dT%H:%M:%S.%f"


def test_records_started_and_finished_timestamps():
    ticks = iter([
        datetime(2025, 1, 1, 10, 0, 0, 123000),
        datetime(2025, 1, 1, 10, 0, 5, 456000),
    ])

    with ProcessTimer(clock=lambda: next(ticks)) as timer:
        pass

    assert timer.started_at == "2025-01-01T10:00:00.123"
    assert timer.finished_at == "2025-01-01T10:00:05.456"


def test_finished_at_is_set_even_if_the_body_raises():
    ticks = iter([
        datetime(2025, 1, 1, 10, 0, 0, 0),
        datetime(2025, 1, 1, 10, 0, 1, 0),
    ])
    timer = ProcessTimer(clock=lambda: next(ticks))

    with pytest.raises(RuntimeError):
        with timer:
            raise RuntimeError("boom")

    assert timer.started_at is not None
    assert timer.finished_at is not None
