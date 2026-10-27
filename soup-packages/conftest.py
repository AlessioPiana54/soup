"""
------------------------------------------------------------------------
File : conftest.py
Description: pytest configuration for the tests kept next to the
             packages (soup-packages/<name>/tests), run from soup-server/
             (its pytest.ini collects them): soup-server/ goes on sys.path,
             so they use the host (soup.core) and the shared test helpers
             (tests.fakes, tests.packages) like the tests in
             soup-server/tests. Not part of any package zip (only
             soup-package.json, server/ and app/dist/ are packed).
Project : soup-packages
------------------------------------------------------------------------
"""

import sys
from pathlib import Path

import pytest

SERVER_ROOT = Path(__file__).resolve().parent.parent / "soup-server"

if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

FIXTURES_DIR = SERVER_ROOT / "tests" / "fixtures"


@pytest.fixture
def sample_event_log_csv() -> Path:
    """The realistic/dirty sample event log CSV (soup-server/tests/fixtures)."""

    return FIXTURES_DIR / "sample_event_log.csv"
