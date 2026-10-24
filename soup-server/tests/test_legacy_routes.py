"""
------------------------------------------------------------------------
File : test_legacy_routes.py
Description: Checks the shape of the auto-extracted legacy routes fixture
             (tests/fixtures/legacy_routes.json), and - now that
             soup/api/flask_app.py exists - that every one of those
             routes is still served by the new app, with the same HTTP
             method (POST /api/v2/graph is now backed by the new import
             pipeline instead of Controllers/Graph/graph_controller.py,
             but the path+method themselves are unchanged).
Project : soup-server
------------------------------------------------------------------------
"""

import json

import pytest

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


def _legacy_routes(legacy_routes_json):
    return json.loads(legacy_routes_json.read_text(encoding="utf-8"))


@pytest.fixture
def new_app():
    from soup.api.flask_app import build_flask_app
    from soup.core.engine import build_engine
    from soup.core.settings import Settings
    from tests.fakes import FakeDatabase, InMemoryFileStorage

    settings = Settings.from_env({"SOUP_PACKAGES": "csv_reader"})
    engine = build_engine(settings, db=FakeDatabase(), storage=InMemoryFileStorage())
    return build_flask_app(engine)


def test_every_legacy_route_is_still_served_by_the_new_app(legacy_routes_json, new_app):
    routes = _legacy_routes(legacy_routes_json)
    served = [(rule.rule, method) for rule in new_app.url_map.iter_rules() for method in rule.methods]

    missing = [
        f"{entry['method']} {entry['path']}"
        for entry in routes
        if (entry["path"], entry["method"]) not in served
    ]
    assert missing == [], f"routes no longer served by the new app: {missing}"
