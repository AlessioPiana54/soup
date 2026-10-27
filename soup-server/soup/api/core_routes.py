"""
------------------------------------------------------------------------
File : core_routes.py
Description: The /api/v2 routes the new host owns directly (until the
             old pages go, commit 11):
             - POST /api/v2/graph: replaces Controllers/Graph/
               graph_controller.py's create_graph(). Same method, path,
               form fields (dataset_name, dataset_description,
               all_columns, standardColumn, filteredColumn, valuesColumn,
               trigger_N/target_N, process_execution) and the same
               success status/message/response_data shape. It runs the
               csv_ekg package's importer through the ImportRouter, the
               old form fields translated into its options: the dataset
               becomes an "ekg" object of the catalog, its folder named
               after dataset_name. `copy_file` is accepted if present
               but ignored (the uploaded `file` is read once).
             - POST /api/v2/complete-graph/build: replaces
               Controllers/generic_graph_controller.py's
               create_dataset_graphs(), which rebuilt the graph of a
               dataset from its files: it finds the dataset's "ekg"
               object and runs the ekg package's "load" operation
               (ensure_loaded, with force: the old pages also change the
               graph outside the memgraph tool's state).
             - GET /api/v2/welcome, GET /api/v2/memgraph-connect:
               reproduced from app.py. memgraph-connect pings the
               "memgraph" tool: without it the answer is 503.
             Without the packages (csv_ekg, ekg) these routes answer 503.

             Domain errors (soup.core.contracts.DomainError) are not caught
             here - they propagate to the single error handler registered
             in flask_app.py, which turns them into the right HTTP
             response. soup/api is the only place in soup/ that imports
             Flask.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import json
from typing import Any

from flask import Blueprint, jsonify, request

from soup.core.contracts import (
    GraphDatabase,
    NotFoundError,
    Query,
    ServiceUnavailableError,
    Upload,
    ValidationError,
)
from soup.core.engine import Engine
from soup.core.results import Result

CORE_ROUTES_BLUEPRINT_NAME = "core_routes_bp"

_MEMGRAPH_PING_QUERY = Query("RETURN 1")

# What the v2 routes run: keys of package contributions, not imports.
CSV_EKG_IMPORTER = "csv_ekg.csv"
EKG_LOAD_OPERATION = "ekg.load"
EKG_KIND = "ekg"
MEMGRAPH_TOOL = "memgraph"


def _json_form_field(name: str, default: Any) -> Any:
    raw = request.form.get(name)
    if raw is None:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"Form field '{name}' is not valid JSON: {exc.msg}") from None


def _trigger_target_pairs() -> list[list[str]]:
    pairs = []
    index = 0
    while f"trigger_{index}" in request.form and f"target_{index}" in request.form:
        pairs.append([request.form.get(f"trigger_{index}"), request.form.get(f"target_{index}")])
        index += 1
    return pairs


def _graph_options() -> dict[str, Any]:
    """The old form fields as options of the csv_ekg importer."""

    standard_columns = _json_form_field("standardColumn", [])
    if not isinstance(standard_columns, list) or len(standard_columns) != 3:
        raise ValidationError("'standardColumn' must have exactly 3 entries: [event_id, timestamp, activity]")
    event_id, timestamp, activity = standard_columns
    return {
        "event_id": event_id,
        "timestamp": timestamp,
        "activity": activity,
        "entities": _json_form_field("filteredColumn", []),
        "values": _json_form_field("valuesColumn", []),
        "trigger_target": _trigger_target_pairs(),
        "save_process_times": request.form.get("process_execution", "false").strip().lower() == "true",
        "dataset": request.form.get("dataset_name"),
        "all_columns": _json_form_field("all_columns", None),
    }


def _ekg_object(engine: Engine, dataset_name: Any):
    """The root "ekg" object of a dataset folder, or None."""

    for obj in engine.core_tools.catalog().list():
        if obj.kind == EKG_KIND and obj.meta.get("dataset") == dataset_name and "state" not in obj.meta:
            return obj
    return None


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

        options = _graph_options()
        try:
            engine.import_router.get(CSV_EKG_IMPORTER)
        except NotFoundError:
            raise ServiceUnavailableError(
                "The event log import is not available: the csv_ekg package (and the ekg package and "
                "the 'memgraph' and 'storage' tools it requires) must be active"
            ) from None
        engine.import_router.import_(
            CSV_EKG_IMPORTER,
            Upload(file.filename, file.stream, file.mimetype or ""),
            name=request.form.get("dataset_name") or "",
            description=request.form.get("dataset_description") or "",
            options=options,
        )
        result = Result(http_status_code=201, message="Create graph successfully", response_data="success")
        return jsonify(result.to_dict()), 201

    @blueprint.route("/api/v2/complete-graph/build", methods=["POST"])
    def create_dataset_graphs():
        data = request.get_json(silent=True, force=True) or {}
        obj = _ekg_object(engine, data.get("dataset_name"))
        if obj is None:
            result = Result(404, "Unable to create the Dataset graphs", f"Dataset '{data.get('dataset_name')}' not found")
            return jsonify(result.to_dict()), 404
        try:
            engine.operation_router.run(EKG_LOAD_OPERATION, [obj.id], {"force": True})
        except NotFoundError:
            raise ServiceUnavailableError(
                "The graph cannot be built: the ekg package (and the 'memgraph' and 'storage' tools) must be active"
            ) from None
        result = Result(200, "Successfully created the Dataset graphs", "success")
        return jsonify(result.to_dict()), 200

    @blueprint.route("/api/v2/welcome", methods=["GET"])
    def welcome_api():
        result = Result(200, "Hello user, the Engine work :)")
        return jsonify(result.to_dict()), 200

    @blueprint.route("/api/v2/memgraph-connect", methods=["GET"])
    def connect_database():
        tools = engine.core_tools.toolbox("route /api/v2/memgraph-connect", (MEMGRAPH_TOOL,))
        rows = tools.typed(MEMGRAPH_TOOL, GraphDatabase).run(_MEMGRAPH_PING_QUERY)

        if not rows:
            result = Result(500, "Error while connecting to Memgraph")
            return jsonify(result.to_dict()), 500

        result = Result(200, "Success connect with Memgraph", rows)
        return jsonify(result.to_dict()), 200

    return blueprint
