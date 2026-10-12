"""
------------------------------------------------------------------------
File : test_process_timer.py
Description: Tests for ProcessTimer (soup.core.process_timer).
Project : soup-server
------------------------------------------------------------------------
"""

from datetime import datetime

import pytest

from soup.core.process_timer import DATE_FORMAT, ProcessTimer


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
