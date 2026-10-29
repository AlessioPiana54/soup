"""
------------------------------------------------------------------------
File : test_wsgi_entrypoint.py
Description: The production entrypoint (wsgi.py): the Flask app of an
             Engine built from the environment, Engine.shutdown()
             registered for the exit, served by waitress in one process
             with several threads on 0.0.0.0:8080.
Project : soup-server
------------------------------------------------------------------------
"""

import wsgi
from tests.api_client import code_client


def test_create_app_builds_the_engine_from_the_environment_and_registers_its_shutdown(monkeypatch):
    _, engine, _ = code_client()
    settings, registered = [], []
    monkeypatch.setattr(wsgi, "build_engine", lambda value: settings.append(value) or engine)
    monkeypatch.setattr(wsgi.atexit, "register", registered.append)

    app = wsgi.create_app()

    assert len(settings) == 1
    assert registered == [engine.shutdown]
    assert app.test_client().get("/api/v3/health").status_code == 200


def test_main_serves_one_process_with_several_threads(monkeypatch):
    app = object()
    served = []
    monkeypatch.setattr(wsgi, "create_app", lambda: app)
    monkeypatch.setattr(wsgi, "serve", lambda *args, **kwargs: served.append((args, kwargs)))

    wsgi.main()

    assert served == [((app,), {"host": "0.0.0.0", "port": 8080, "threads": 8})]
