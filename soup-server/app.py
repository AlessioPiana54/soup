"""
------------------------------------------------------------------------
File : app.py
Description: Process entrypoint. Builds the Engine (soup.core.engine)
             and the Flask app that serves it (soup.api.flask_app),
             registers Engine.shutdown() to run on process exit (closes
             the database driver, shuts down plugins), and runs the app.
             Debug mode only with SOUP_DEBUG=1/true: the Werkzeug
             debugger runs Python code for whoever reaches the port. The
             reloader is always off, so the engine is built once.
Date creation: 20-02-2024
Project : soup-server
Author: Alessio Giacché
Copyright: Copyright (c) 2024 Alessio Giacché <ale.giacc.dev@gmail.com>
License : MIT
------------------------------------------------------------------------
"""

import atexit
import os
from collections.abc import Mapping

from soup.api.flask_app import build_flask_app
from soup.core.engine import build_engine
from soup.core.settings import Settings


def debug_from_env(env: Mapping[str, str]) -> bool:
    """SOUP_DEBUG set to "1" or "true" (any case); off otherwise."""

    return env.get("SOUP_DEBUG", "").strip().lower() in ("1", "true")


if __name__ == '__main__':
    engine = build_engine(Settings.from_env())
    atexit.register(engine.shutdown)

    app = build_flask_app(engine)
    app.run(host='0.0.0.0', port=8080, debug=debug_from_env(os.environ), use_reloader=False)
