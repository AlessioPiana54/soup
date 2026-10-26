"""
------------------------------------------------------------------------
File : e2e_server.py
Description: The backend of the frontend end-to-end tests
             (soup-app/e2e, Playwright): a real Flask app on an engine
             with the in-memory catalog and preferences (CoreToolsPackage)
             and no bundled package, in throw-away folders, with package
             installation allowed. No Docker, no Memgraph: the tests
             install the packages they need from zips. Not a test module
             (pytest does not collect it).
             Run from soup-server/: python -m tests.e2e_server
             (SOUP_E2E_PORT, default 8080; npm run e2e uses 8081).
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from soup.api.flask_app import build_flask_app
from soup.core.engine import build_engine
from soup.core.settings import Settings
from tests.fakes import CoreToolsPackage


def main() -> None:
    root = Path(tempfile.mkdtemp(prefix="soup-e2e-"))
    bundled, installed = root / "bundled", root / "installed"
    bundled.mkdir()
    settings = Settings(
        packages_path=(str(bundled), str(installed)),
        installed_packages_dir=str(installed),
        allow_package_install=True,
    )
    engine = build_engine(settings, extra_plugins=[CoreToolsPackage()])
    app = build_flask_app(engine)
    port = int(os.environ.get("SOUP_E2E_PORT", "8080"))
    print(f"SOUP e2e backend on http://127.0.0.1:{port} (data in {root})", flush=True)
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
