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
# packaged (no setup.py/pyproject.toml, no __init__.py under Controllers/
# Services/Models/Utils/Shared), so its modules are imported as top-level
# namespace packages (e.g. `from Services.dataset_service import ...`).
# Importing them in tests therefore requires soup-server/ on sys.path.
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
def legacy_routes_json(fixtures_dir: Path) -> Path:
    """Path to the auto-extracted legacy routes JSON fixture."""

    return fixtures_dir / "legacy_routes.json"
