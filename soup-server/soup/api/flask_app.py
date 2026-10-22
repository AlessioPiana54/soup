"""
------------------------------------------------------------------------
File : flask_app.py
Description: build_flask_app(engine) assembles the Flask app: every
             legacy blueprint (Controllers/*) is registered WITHOUT
             modification, except Controllers/Graph/graph_controller.py's
             old POST /api/v2/graph, which core_routes.py replaces at the
             identical path/method with the new ImportService-backed
             implementation (soup/core). This module - together with
             core_routes.py - is the only place in soup/ that imports
             Flask; soup/core and soup/plugins never do.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import logging

from flask import Flask, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO
from werkzeug.exceptions import HTTPException

from soup.api.core_routes import build_core_blueprint
from soup.core.engine import Engine
from soup.core.contracts.errors import DomainError
from soup.core.results import Result


def build_flask_app(engine: Engine) -> Flask:
    app = Flask(__name__)

    _register_legacy_blueprints(app)
    app.register_blueprint(build_core_blueprint(engine))
    _register_error_handlers(app)

    socketio = SocketIO(app, cors_allowed_origins="*")
    app.config["socketio"] = socketio
    CORS(app)

    log = logging.getLogger("werkzeug")
    log.setLevel(logging.ERROR)

    return app


def _register_legacy_blueprints(app: Flask) -> None:
    """
    Every blueprint app.py registers today, unmodified, EXCEPT
    Controllers.Graph.graph_controller (the old POST /api/v2/graph) -
    core_routes.py now serves that exact path/method instead. Imported
    here (not at module load time) so importing soup.api.flask_app does
    not require the legacy Controllers/Services tree to be importable
    unless an app is actually being built.
    """

    from Controllers.AggregateGraph.aggregate_graph_controller import aggregate_graph_controller_bp
    from Controllers.AggregateGraph.aggregate_graph_op_controller import aggregate_graph_op_controller_bp
    from Controllers.dataset_controller import dataset_controller_bp
    from Controllers.filters_controller import filters_controller_bp
    from Controllers.generic_graph_controller import generic_graph_controller_bp
    from Controllers.Graph.graph_op_controller import graph_op_controller_bp
    from Controllers.graph_json_controller import graph_json_controller_bp
    from Controllers.onboarding_controller import onboarding_controller_bp

    app.register_blueprint(graph_op_controller_bp)
    app.register_blueprint(aggregate_graph_controller_bp)
    app.register_blueprint(aggregate_graph_op_controller_bp)
    app.register_blueprint(generic_graph_controller_bp)
    app.register_blueprint(graph_json_controller_bp)
    app.register_blueprint(dataset_controller_bp)
    app.register_blueprint(filters_controller_bp)
    app.register_blueprint(onboarding_controller_bp)


def _register_error_handlers(app: Flask) -> None:
    """One place that turns an exception into an HTTP response."""

    @app.errorhandler(DomainError)
    def _handle_domain_error(error: DomainError):
        result = Result(error.http_status_code, str(error))
        return jsonify(result.to_dict()), error.http_status_code

    @app.errorhandler(HTTPException)
    def _handle_http_exception(error: HTTPException):
        # Flask/Werkzeug's own routing errors (404 Not Found, 405 Method
        # Not Allowed, ...) are already well-formed responses - let them
        # through as-is instead of flattening them into a 500.
        return error

    @app.errorhandler(Exception)
    def _handle_unexpected_error(error: Exception):
        result = Result(500, f"Internal Server Error: {error}")
        return jsonify(result.to_dict()), 500
