"""
------------------------------------------------------------------------
File : process_timer.py
Description: ProcessTimer - context manager recording start/end
             timestamps in the exact date format used today throughout
             the config JSON (Services/generic_graph_service.py,
             Services/dataset_service.py):
             datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3]
             e.g. "2025-01-01T10:00:00.123" (ISO-8601, no timezone,
             3-digit milliseconds instead of the 6-digit %f microseconds).
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional

DATE_FORMAT = "%Y-%m-%dT%H:%M:%S.%f"


class ProcessTimer:
    """
    Usage:
        with ProcessTimer() as timer:
            ... do work ...
        timer.started_at  # "2025-01-01T10:00:00.123"
        timer.finished_at

    `clock` is injectable for tests (defaults to datetime.now).
    """

    def __init__(self, clock: Callable[[], datetime] = datetime.now):
        self._clock = clock
        self.started_at: Optional[str] = None
        self.finished_at: Optional[str] = None

    def __enter__(self) -> "ProcessTimer":
        self.started_at = self._now()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.finished_at = self._now()
        return False

    def _now(self) -> str:
        # [:-3] trims the 6-digit %f microseconds down to 3-digit
        # milliseconds, matching the legacy format exactly.
        return self._clock().strftime(DATE_FORMAT)[:-3]
