"""
------------------------------------------------------------------------
File : system_routes.py
Description: /api/v3 preferences, tools and health, delegating to
             SystemService:
             - GET /api/v3/preferences/<key>   {key, value} (null if never set)
             - PUT /api/v3/preferences/<key>   JSON {value}
             - GET /api/v3/tools               loaded tools, package, health
             - GET /api/v3/health              {status: ok|degraded, tools,
                                               problems}; always 200, the
                                               status is in the body
             Domain errors propagate to the handler in flask_app.py.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from flask import Blueprint

from soup.api import request_args, serializers
from soup.core.contracts import ValidationError
from soup.core.engine import Engine

SYSTEM_ROUTES_BLUEPRINT_NAME = "system_routes_bp"


def build_system_blueprint(engine: Engine) -> Blueprint:
    blueprint = Blueprint(SYSTEM_ROUTES_BLUEPRINT_NAME, __name__)
    system = engine.system

    @blueprint.route("/api/v3/preferences/<key>", methods=["GET"])
    def get_preference(key: str):
        return serializers.ok("Preference", {"key": key, "value": system.get_preference(key)})

    @blueprint.route("/api/v3/preferences/<key>", methods=["PUT"])
    def set_preference(key: str):
        body = request_args.json_body()
        if "value" not in body:
            raise ValidationError("The request body must be a JSON object {\"value\": ...}")
        system.set_preference(key, body["value"])
        return serializers.ok("Preference saved", {"key": key, "value": body["value"]})

    @blueprint.route("/api/v3/tools", methods=["GET"])
    def list_tools():
        return serializers.ok("Tools", [serializers.tool_status(tool) for tool in system.tools()])

    @blueprint.route("/api/v3/health", methods=["GET"])
    def health():
        return serializers.ok("Health", serializers.health(system.health()))

    return blueprint
