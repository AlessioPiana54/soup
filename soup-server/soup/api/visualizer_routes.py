"""
------------------------------------------------------------------------
File : visualizer_routes.py
Description: /api/v3/objects/<id>/visualizers and /exporters, delegating
             to VisualizerRouter and ExportRouter:
             - GET  .../visualizers                       [{id, label, package,
                                                          element, module_url}]
             - GET  .../visualizers/<vid>/data            ?params (JSON answer)
             - POST .../visualizers/<vid>/actions/<name>  JSON params
             - GET  .../exporters                         with their fields
             - GET  .../export/<eid>?params               the file, as an
                                                          attachment
             GET parameters are ?params=<json> or the flat query
             arguments. Domain errors propagate to the handler in
             flask_app.py.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import io

from flask import Blueprint, send_file

from soup.api import request_args, serializers
from soup.core.engine import Engine

VISUALIZER_ROUTES_BLUEPRINT_NAME = "visualizer_routes_bp"


def build_visualizer_blueprint(engine: Engine) -> Blueprint:
    blueprint = Blueprint(VISUALIZER_ROUTES_BLUEPRINT_NAME, __name__)
    visualizers = engine.visualizer_router
    exporters = engine.export_router
    frontend = engine.frontend

    @blueprint.route("/api/v3/objects/<object_id>/visualizers", methods=["GET"])
    def list_visualizers(object_id: str):
        return serializers.ok("Visualizers", [
            serializers.visualizer(entry, serializers.module_url(entry.package, frontend.entry(entry.package)))
            for entry in visualizers.visualizers_for(object_id)
        ])

    @blueprint.route("/api/v3/objects/<object_id>/visualizers/<visualizer_id>/data", methods=["GET"])
    def visualizer_data(object_id: str, visualizer_id: str):
        return serializers.ok("Data", visualizers.data(visualizer_id, object_id, request_args.query_params()))

    @blueprint.route("/api/v3/objects/<object_id>/visualizers/<visualizer_id>/actions/<name>", methods=["POST"])
    def visualizer_action(object_id: str, visualizer_id: str, name: str):
        return serializers.ok("Action", visualizers.action(visualizer_id, object_id, name, request_args.json_body()))

    @blueprint.route("/api/v3/objects/<object_id>/exporters", methods=["GET"])
    def list_exporters(object_id: str):
        return serializers.ok("Exporters", [
            serializers.exporter(entry, exporters.fields(entry.key, object_id))
            for entry in exporters.exporters_for(object_id)
        ])

    @blueprint.route("/api/v3/objects/<object_id>/export/<exporter_id>", methods=["GET"])
    def export_object(object_id: str, exporter_id: str):
        exported = exporters.export(exporter_id, object_id, request_args.query_params())
        return send_file(
            io.BytesIO(exported.content),
            mimetype=exported.mime,
            as_attachment=True,
            download_name=exported.filename,
        )

    return blueprint
