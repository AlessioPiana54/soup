"""
------------------------------------------------------------------------
File : flask_app.py
Description: build_flask_app(engine) assembles the Flask app: every
             legacy blueprint (Controllers/*) is registered WITHOUT
             modification, except Controllers/Graph/graph_controller.py's
             old POST /api/v2/graph, which core_routes.py replaces at the
             identical path/method (the csv_ekg importer), and
             POST /api/v2/complete-graph/build, which core_routes.py
             serves instead of generic_graph_controller.py (registered
             first, so its rule wins; the ekg package's "load"
             operation). The legacy routes that change the graph do it
             outside the memgraph tool's state: after every non-GET
             /api/v2 request they serve, the tool forgets its state, so
             the next ensure_loaded rebuilds. Plus the /api/v3 routes
             (workspace, import, operation, visualizer, package and
             system blueprints), thin wrappers around the core routers
             that serialize through serializers.py. Request bodies under
             /api/v3 are capped at Settings.max_upload_mb (413); the v2
             routes keep having no limit. soup/api is the only place in
             soup/ that imports Flask; soup/core and the packages never
             do.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import logging

from typing import Optional

from flask import Flask, Request, current_app, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO
from werkzeug.exceptions import HTTPException

from soup.api.core_routes import CORE_ROUTES_BLUEPRINT_NAME, MEMGRAPH_TOOL, build_core_blueprint
from soup.api.import_routes import build_import_blueprint
from soup.api.operation_routes import build_operation_blueprint
from soup.api.package_routes import build_package_blueprint
from soup.api.system_routes import build_system_blueprint
from soup.api.visualizer_routes import build_visualizer_blueprint
from soup.api.workspace_routes import build_workspace_blueprint
from soup.core.engine import Engine
from soup.core.contracts.errors import DomainError
from soup.core.results import Result


V2_PREFIX = "/api/v2/"
V3_PREFIX = "/api/v3/"
V3_MAX_CONTENT_LENGTH = "SOUP_V3_MAX_CONTENT_LENGTH"


class SoupRequest(Request):
    """
    Flask 2.3 has a single, app-wide MAX_CONTENT_LENGTH: this request
    applies the upload limit to /api/v3 only, so the v2 routes behave as
    before. Werkzeug answers 413 when the body is larger.
    """

    @property
    def max_content_length(self) -> Optional[int]:  # type: ignore[override]
        if self.path.startswith(V3_PREFIX):
            return current_app.config.get(V3_MAX_CONTENT_LENGTH)
        return super().max_content_length


def build_flask_app(engine: Engine) -> Flask:
    app = Flask(__name__)
    app.request_class = SoupRequest
    app.config[V3_MAX_CONTENT_LENGTH] = engine.settings.max_upload_bytes

    app.register_blueprint(build_core_blueprint(engine))
    _register_legacy_blueprints(app)
    _register_legacy_state_guard(app, engine)
    app.register_blueprint(build_package_blueprint(engine))
    app.register_blueprint(build_workspace_blueprint(engine))
    app.register_blueprint(build_import_blueprint(engine))
    app.register_blueprint(build_operation_blueprint(engine))
    app.register_blueprint(build_visualizer_blueprint(engine))
    app.register_blueprint(build_system_blueprint(engine))
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


def _register_legacy_state_guard(app: Flask, engine: Engine) -> None:
    """After a legacy /api/v2 request that may change the graph, the memgraph tool forgets its state."""

    @app.after_request
    def _forget_graph_state(response):
        if (
            request.path.startswith(V2_PREFIX)
            and request.method != "GET"
            and request.blueprint != CORE_ROUTES_BLUEPRINT_NAME
        ):
            invalidate = getattr(engine.ctx.tool_registry.get(MEMGRAPH_TOOL), "invalidate", None)
            if callable(invalidate):
                invalidate()
        return response


def _register_error_handlers(app: Flask) -> None:
    """One place that turns an exception into an HTTP response."""

    @app.errorhandler(DomainError)
    def _handle_domain_error(error: DomainError):
        # `details` (e.g. the packages blocking a disable) go in response_data.
        result = Result(error.http_status_code, str(error), error.details or None)
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
