"""
------------------------------------------------------------------------
File : test_legacy_routes.py
Description: The routes the app serves are exactly the saved /api/v3
             list (tests/fixtures/api_v3_routes.json, regenerated with
             tests/tools/dump_v3_routes.py): the /api/v2 routes of the
             old pages are gone and none comes back by accident.
Project : soup-server
------------------------------------------------------------------------
"""

import json

import pytest

from tests.tools.dump_v3_routes import build_app, served_routes

VALID_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH"}


@pytest.fixture
def saved_routes(api_v3_routes_json):
    assert api_v3_routes_json.exists(), (
        f"{api_v3_routes_json} not found - run `python -m tests.tools.dump_v3_routes` from soup-server/"
    )
    return json.loads(api_v3_routes_json.read_text(encoding="utf-8"))


def test_saved_routes_are_all_v3(saved_routes):
    assert saved_routes
    for entry in saved_routes:
        assert set(entry) == {"method", "path"}
        assert entry["method"] in VALID_METHODS
        assert entry["path"].startswith("/api/v3/")


def test_the_app_serves_exactly_the_saved_v3_routes(saved_routes):
    served = served_routes(build_app())

    def key(entry):
        return entry["method"], entry["path"]

    missing = sorted(set(map(key, saved_routes)) - set(map(key, served)))
    extra = sorted(set(map(key, served)) - set(map(key, saved_routes)))
    assert missing == [], f"v3 routes no longer served: {missing}"
    assert extra == [], f"routes not in api_v3_routes.json: {extra}"


def test_no_v2_route_is_served():
    assert [entry for entry in served_routes(build_app()) if "/api/v2" in entry["path"]] == []
