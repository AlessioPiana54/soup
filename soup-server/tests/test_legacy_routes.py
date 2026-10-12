"""
------------------------------------------------------------------------
File : test_legacy_routes.py
Description: Checks the shape of the auto-extracted legacy routes fixture
             (tests/fixtures/legacy_routes.json). It does not yet assert
             anything about actual request/response behaviour - that will
             be added once the Pilastro 1 (Import) plugin work starts and
             a Flask test client fixture is available.
Project : soup-server
------------------------------------------------------------------------
"""

import json

VALID_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH"}
EXPECTED_KEYS = {"method", "path", "source_file", "handler"}


def test_legacy_routes_file_exists(legacy_routes_json):
    assert legacy_routes_json.exists(), (
        f"{legacy_routes_json} not found - run "
        "tests/tools/extract_legacy_routes.py from soup-server/ to generate it"
    )


def test_legacy_routes_file_is_not_empty(legacy_routes_json):
    routes = json.loads(legacy_routes_json.read_text(encoding="utf-8"))
    assert isinstance(routes, list)
    assert len(routes) > 0


def test_legacy_routes_entries_have_expected_structure(legacy_routes_json):
    routes = json.loads(legacy_routes_json.read_text(encoding="utf-8"))

    for entry in routes:
        assert isinstance(entry, dict)
        assert EXPECTED_KEYS.issubset(entry.keys())

        assert isinstance(entry["method"], str)
        assert isinstance(entry["path"], str)
        assert isinstance(entry["source_file"], str)
        assert isinstance(entry["handler"], str)

        assert entry["method"] in VALID_METHODS
        assert entry["path"].startswith("/api/v2/")
        assert entry["handler"] != ""
        assert entry["source_file"] != ""
