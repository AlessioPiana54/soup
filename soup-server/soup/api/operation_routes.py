"""
------------------------------------------------------------------------
File : operation_routes.py
Description: /api/v3/operations - the actions offered for a selection of
             objects, delegating to OperationRouter:
             - GET  /api/v3/operations?objects=id1,id2   applicable operations
             - GET  /api/v3/operations/<op_id>/fields?objects=...
             - POST /api/v3/operations/<op_id>/run       JSON {objects, params}
                    -> [ObjectRef created], 201
             `objects` in run is a list of ids (matched to the input
             slots like in the listing) or a {slot name: id} mapping.
             Domain errors propagate to the handler in flask_app.py.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from flask import Blueprint
from flask.typing import ResponseReturnValue

from soup.api import request_args, serializers
from soup.core.engine import Engine

OPERATION_ROUTES_BLUEPRINT_NAME = "operation_routes_bp"


def build_operation_blueprint(engine: Engine) -> Blueprint:
    blueprint = Blueprint(OPERATION_ROUTES_BLUEPRINT_NAME, __name__)
    operations = engine.operation_router

    @blueprint.route("/api/v3/operations", methods=["GET"])
    def list_operations() -> ResponseReturnValue:
        entries = operations.operations_for(request_args.object_ids())
        return serializers.ok("Operations", [serializers.operation(entry) for entry in entries])

    @blueprint.route("/api/v3/operations/<op_id>/fields", methods=["GET"])
    def operation_fields(op_id: str) -> ResponseReturnValue:
        return serializers.ok("Fields", serializers.fields(operations.fields(op_id, request_args.object_ids())))

    @blueprint.route("/api/v3/operations/<op_id>/run", methods=["POST"])
    def run_operation(op_id: str) -> ResponseReturnValue:
        body = request_args.json_body()
        outputs = operations.run(op_id, request_args.selection(body), body.get("params"))
        return serializers.ok(f"Operation '{op_id}' completed", serializers.object_refs(outputs), 201)

    return blueprint
