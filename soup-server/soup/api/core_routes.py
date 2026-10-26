"""
------------------------------------------------------------------------
File : core_routes.py
Description: The routes the new host owns directly:
             - POST /api/v2/graph: replaces Controllers/Graph/
               graph_controller.py's create_graph(). Same method, path,
               form fields (dataset_name, dataset_description,
               all_columns, standardColumn, filteredColumn, valuesColumn,
               trigger_N/target_N) and the same success status/message/
               response_data shape. `copy_file` is accepted if present
               (for client compatibility during the transition) but
               ignored - the new pipeline reads the uploaded `file`
               stream once and normalizes it itself, so the legacy
               second upload of the same bytes is redundant. Dispatches
               via ImportService with kind="event_log" and the file's
               original name (so the reader is chosen by its real
               extension, not a hard-coded ".csv" check - see section 11
               of the refactoring document).
             - GET /api/v2/welcome, GET /api/v2/memgraph-connect:
               reproduced from app.py so the new app is a full drop-in
               replacement; every other route keeps living in the
               legacy Controllers/* blueprints, registered unmodified
               (soup/api/flask_app.py). memgraph-connect pings the
               "memgraph" tool: without it the answer is 503.

             Domain errors (soup.core.contracts.DomainError) are not caught
             here - they propagate to the single error handler registered
             in flask_app.py, which turns them into the right HTTP
             response. soup/api is the only place in
             soup/ that imports Flask.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import json
from typing import Any

from flask import Blueprint, jsonify, request

from soup.core.contracts import EVENT_LOG, Query
from soup.core.engine import Engine
from soup.core.results import Result
from soup.core.services.import_service import ImportCommand

CORE_ROUTES_BLUEPRINT_NAME = "core_routes_bp"

_MEMGRAPH_PING_QUERY = Query("RETURN 1")


def _json_form_field(name: str, default: Any) -> Any:
    raw = request.form.get(name)
    if raw is None:
        return default
    return json.loads(raw)


def _trigger_target_rows() -> list[dict]:
    rows = []
    index = 0
    while f"trigger_{index}" in request.form and f"target_{index}" in request.form:
        rows.append({
            "trigger": request.form.get(f"trigger_{index}"),
            "target": request.form.get(f"target_{index}"),
        })
        index += 1
    return rows


def build_core_blueprint(engine: Engine) -> Blueprint:
    blueprint = Blueprint(CORE_ROUTES_BLUEPRINT_NAME, __name__)

    @blueprint.route("/api/v2/graph", methods=["POST"])
    def create_graph():
        if "file" not in request.files or request.files["file"] is None:
            return jsonify(Result(400, "Bad request. File not found").to_dict()), 400

        file = request.files["file"]
        if not file or not file.filename:
            return jsonify(Result(400, "Bad request. File not found").to_dict()), 400

        # Accepted but ignored - see module docstring.
        request.files.get("copy_file")

        command = ImportCommand(
            filename=file.filename,
            stream=file.stream,
            kind=EVENT_LOG,
            options={
                "dataset_name": request.form.get("dataset_name"),
                "dataset_description": request.form.get("dataset_description"),
                "all_columns": _json_form_field("all_columns", []),
                "standard_columns": _json_form_field("standardColumn", []),
                "filtered_columns": _json_form_field("filteredColumn", []),
                "values_columns": _json_form_field("valuesColumn", []),
                "trigger_target_rows": _trigger_target_rows(),
            },
        )

        result = engine.import_service.import_(command)
        return jsonify(result.to_dict()), result.http_status_code

    @blueprint.route("/api/v2/welcome", methods=["GET"])
    def welcome_api():
        result = Result(200, "Hello user, the Engine work :)")
        return jsonify(result.to_dict()), 200

    @blueprint.route("/api/v2/memgraph-connect", methods=["GET"])
    def connect_database():
        rows = engine.core_tools.graph().run(_MEMGRAPH_PING_QUERY)

        if not rows:
            result = Result(500, "Error while connecting to Memgraph")
            return jsonify(result.to_dict()), 500

        result = Result(200, "Success connect with Memgraph", rows)
        return jsonify(result.to_dict()), 200

    return blueprint
