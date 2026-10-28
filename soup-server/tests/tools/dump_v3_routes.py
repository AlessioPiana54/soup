"""
------------------------------------------------------------------------
File : dump_v3_routes.py
Description: Writes tests/fixtures/api_v3_routes.json, the routes the app
             serves ({method, path}, sorted, without HEAD/OPTIONS and the
             Flask static route), built with no packages loaded: the
             routes belong to soup/api, not to the packages.
             tests/test_legacy_routes.py compares the app with this list,
             so a route added or removed on purpose means running, from
             soup-server/:  python -m tests.tools.dump_v3_routes
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import json
from pathlib import Path

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "api_v3_routes.json"
IGNORED_METHODS = {"HEAD", "OPTIONS"}


def served_routes(app) -> list[dict[str, str]]:
    routes = {
        (rule.rule, method)
        for rule in app.url_map.iter_rules()
        if rule.endpoint != "static"
        for method in rule.methods
        if method not in IGNORED_METHODS
    }
    return [{"method": method, "path": path} for path, method in sorted(routes)]


def build_app():
    from soup.api.flask_app import build_flask_app
    from soup.core.settings import Settings
    from tests.fakes import FakeDatabase, InMemoryFileStorage, fake_tool_engine

    settings = Settings.from_env({"SOUP_PACKAGES": ""})
    return build_flask_app(fake_tool_engine(settings, db=FakeDatabase(), files=InMemoryFileStorage()))


def main() -> None:
    routes = served_routes(build_app())
    FIXTURE.write_text(json.dumps(routes, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(routes)} routes written to {FIXTURE}")


if __name__ == "__main__":
    main()
