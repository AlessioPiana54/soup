"""
------------------------------------------------------------------------
File : wsgi.py
Description: Production entrypoint (the Docker image): the same Engine
             and Flask app as app.py, served by waitress instead of the
             Flask development server. ONE process with several threads:
             the engine keeps its state in memory (loaded packages, the
             active Memgraph graph, caches, locks), so it must not be
             forked into several workers. app.py (app.run) stays for
             local development.
Project : soup-server
------------------------------------------------------------------------
"""

import atexit
import logging

from flask import Flask
from waitress import serve

from soup.api.flask_app import build_flask_app
from soup.core.engine import build_engine
from soup.core.settings import Settings

HOST = "0.0.0.0"
PORT = 8080
# Requests served at the same time (an import building a graph holds one).
THREADS = 8


def create_app() -> Flask:
    """Build the Engine from the environment and its Flask app; Engine.shutdown() runs at exit."""

    engine = build_engine(Settings.from_env())
    atexit.register(engine.shutdown)
    return build_flask_app(engine)


def main() -> None:
    # waitress says where it serves ("Serving on http://0.0.0.0:8080") at
    # INFO: the only logger raised to that level.
    logging.getLogger("waitress").setLevel(logging.INFO)
    serve(create_app(), host=HOST, port=PORT, threads=THREADS)


if __name__ == "__main__":
    main()
