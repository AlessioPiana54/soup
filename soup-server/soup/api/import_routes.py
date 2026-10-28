"""
------------------------------------------------------------------------
File : import_routes.py
Description: /api/v3 import, delegating to ImportRouter. The user picks
             the importer: several may accept the same file.
             - GET  /api/v3/importers?filename=x   importers able to read x
             - POST /api/v3/imports/inspect        multipart file, importer_id
                                                   -> {preview, fields}
             - POST /api/v3/imports/preview        + options (JSON) -> {blocks}
             - POST /api/v3/imports                + name, description,
                                                   options -> ObjectRef, 201
             Domain errors propagate to the handler in flask_app.py.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from flask import Blueprint, request
from flask.typing import ResponseReturnValue

from soup.api import request_args, serializers
from soup.core.engine import Engine

IMPORT_ROUTES_BLUEPRINT_NAME = "import_routes_bp"


def build_import_blueprint(engine: Engine) -> Blueprint:
    blueprint = Blueprint(IMPORT_ROUTES_BLUEPRINT_NAME, __name__)
    importers = engine.import_router
    frontend = engine.frontend

    @blueprint.route("/api/v3/importers", methods=["GET"])
    def list_importers() -> ResponseReturnValue:
        entries = importers.importers_for(request_args.required_arg("filename"))
        return serializers.ok("Importers", [
            serializers.importer(entry, serializers.module_url(entry.package, frontend.entry(entry.package)))
            for entry in entries
        ])

    @blueprint.route("/api/v3/imports/inspect", methods=["POST"])
    def inspect_file() -> ResponseReturnValue:
        inspection = importers.inspect(request_args.required_form("importer_id"), request_args.upload())
        return serializers.ok("Inspection", serializers.inspection(inspection))

    @blueprint.route("/api/v3/imports/preview", methods=["POST"])
    def preview_file() -> ResponseReturnValue:
        blocks = importers.preview(
            request_args.required_form("importer_id"), request_args.upload(), request_args.json_form("options")
        )
        return serializers.ok("Preview", {"blocks": serializers.blocks(blocks)})

    @blueprint.route("/api/v3/imports", methods=["POST"])
    def import_file() -> ResponseReturnValue:
        obj = importers.import_(
            request_args.required_form("importer_id"),
            request_args.upload(),
            name=request.form.get("name", ""),
            description=request.form.get("description", ""),
            options=request_args.json_form("options"),
        )
        return serializers.ok(f"Object '{obj.name}' imported", serializers.object_ref(obj), 201)

    return blueprint
