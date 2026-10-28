"""
------------------------------------------------------------------------
File : conftest.py
Description: Shared pytest configuration and fixtures for soup-server.
Project : soup-server
------------------------------------------------------------------------
"""

import sys
from pathlib import Path

import pytest

# soup-server root (parent of this tests/ package). The project is not
# packaged (no setup.py/pyproject.toml), so `soup` and `tests` are imported
# from soup-server/, which therefore goes on sys.path.
SERVER_ROOT = Path(__file__).resolve().parent.parent

if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

TESTS_ROOT = Path(__file__).resolve().parent
FIXTURES_DIR = TESTS_ROOT / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    """Path to the tests/fixtures directory."""

    return FIXTURES_DIR


@pytest.fixture
def sample_event_log_csv(fixtures_dir: Path) -> Path:
    """Path to the realistic/dirty sample event log CSV fixture."""

    return fixtures_dir / "sample_event_log.csv"


@pytest.fixture
def api_v3_routes_json(fixtures_dir: Path) -> Path:
    """Path to the saved list of the /api/v3 routes (tests/tools/dump_v3_routes.py)."""

    return fixtures_dir / "api_v3_routes.json"
