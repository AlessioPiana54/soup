"""
------------------------------------------------------------------------
File : plugin.py
Description: Plugin - contributes the "class" view to "ekg.graph_views",
             the queries of the aggregate graph to "ekg.queries", the
             parts "Class nodes", "OBS relationships" and "DF_C
             relationships" to "ekg.json_parts" (all for "ekg_class"
             objects) and the "ekg_class_graph.classes" state provider to
             "ekg.state_providers"; registers the operation "Costruisci
             grafo aggregato" and the visualizers "Grafo aggregato" and
             "Statistiche del grafo aggregato".
             Observer (scheda C6): it subscribes to "ekg.before_reset" and,
             as critical, to "analysis.before_apply" (published by
             ekg_analysis: only the name of the event is needed, not its
             code) and removes its own Class nodes with its own memgraph
             tool, like the legacy process_analysis did with
             delete_class_graph_query before filtering. No other package
             calls the code of this one. Name, version and dependencies
             come from soup-package.json.
Project : soup-packages/ekg_class_graph
------------------------------------------------------------------------
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import soup_pkg_ekg.api as ekg
from soup_pkg_ekg_views.api import GRAPH_VIEWS_POINT, JSON_PARTS_POINT, QUERIES_POINT

from soup.core.contracts import PluginContext, SoupPlugin

from .classes import delete_classes
from .operations import MEMGRAPH, BuildClassGraph
from .provider import ClassStateProvider
from .queries import class_parts, class_queries
from .views import ClassGraphView
from .visualizers import ClassGraphVisualizer, ClassStatsVisualizer

# Published by ekg_analysis before the filters of an analysis run.
ANALYSIS_BEFORE_APPLY = "analysis.before_apply"


class Plugin(SoupPlugin):
    def register(self, ctx: PluginContext) -> None:
        view = ClassGraphView()
        ctx.contribute(GRAPH_VIEWS_POINT, view, key=view.key)
        for query in class_queries():
            ctx.contribute(QUERIES_POINT, query, key=query.key)
        for part in class_parts():
            ctx.contribute(JSON_PARTS_POINT, part, key=part.key)
        provider = ClassStateProvider()
        ctx.contribute(ekg.STATE_PROVIDERS_POINT, provider, key=provider.key)

        ctx.add_operation(BuildClassGraph())
        ctx.add_visualizer(ClassGraphVisualizer(ctx.contributions))
        ctx.add_visualizer(ClassStatsVisualizer())

        tools = ctx.tools

        def remove_classes(payload: Mapping[str, Any]) -> None:
            delete_classes(tools.get(MEMGRAPH).run)

        ctx.subscribe(ekg.EKG_BEFORE_RESET, remove_classes)
        ctx.subscribe(ANALYSIS_BEFORE_APPLY, remove_classes, critical=True)
