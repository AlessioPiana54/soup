"""
------------------------------------------------------------------------
File : app.py
Description: Process entrypoint. Builds the Engine (soup.core.engine)
             and the Flask app that serves it (soup.api.flask_app),
             registers Engine.shutdown() to run on process exit (closes
             the database driver, shuts down plugins), and runs the app.
             The legacy Flask app this module used to build directly
             (9 blueprints registered by hand, including the old import
             route) has been removed: every blueprint it registered is
             now registered by soup.api.flask_app.build_flask_app()
             instead, unmodified except for the old import route, which
             soup/api/core_routes.py now serves. Nothing else in the
             project imports `app` or `socketio` from this module.
Date creation: 20-02-2024
Project : soup-server
Author: Alessio Giacché
Copyright: Copyright (c) 2024 Alessio Giacché <ale.giacc.dev@gmail.com>
License : MIT
------------------------------------------------------------------------
"""

import atexit

from soup.api.flask_app import build_flask_app
from soup.core.engine import build_engine
from soup.core.settings import Settings

if __name__ == '__main__':
    engine = build_engine(Settings.from_env())
    atexit.register(engine.shutdown)

    app = build_flask_app(engine)
    app.run(host='0.0.0.0', port=8080, debug=True)
