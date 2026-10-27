"""
------------------------------------------------------------------------
File : api.py
Description: Public API of the ekg_views package. Other packages import it
             as soup_pkg_ekg_views.api, and only if they list "ekg_views"
             in their `requires`, to contribute to its extension points:
             - GRAPH_VIEWS_POINT ("ekg.graph_views"): GraphView, or
               EdgeListGraphView for the relationships of some types
               between nodes of some labels (StandardGraphView is the
               one of ekg_views);
             - QUERIES_POINT ("ekg.queries"): GraphQuery, or the bases
               CountQuery, NodeListQuery, RelationshipListQuery;
             - JSON_PARTS_POINT ("ekg.json_parts"): JsonPart;
             with ctx.contribute(POINT, item, key=item.key). Each item
             declares the object kinds it applies to (`kinds`, default
             ("ekg",); STANDARD_KINDS for the ones of ekg_views).
             GraphVisualizer is the "Grafo" visualizer, to subclass for
             the objects of another kind with its own element. clean()
             makes the values read from Memgraph JSON-ready.
Project : soup-packages/ekg_views
------------------------------------------------------------------------
"""

from .contributions import GRAPH_VIEWS_POINT, JSON_PARTS_POINT, QUERIES_POINT, GraphVisualizer, notice_of
from .kinds import DEFAULT_KINDS, STANDARD_KINDS
from .json_parts import JsonPart, NodesPart, RelationshipsPart
from .queries import CountQuery, GraphQuery, NodeListQuery, RelationshipListQuery, count_of
from .values import clean
from .views import EdgeListGraphView, GraphView, StandardGraphView

__all__ = [
    "DEFAULT_KINDS",
    "GRAPH_VIEWS_POINT",
    "JSON_PARTS_POINT",
    "QUERIES_POINT",
    "STANDARD_KINDS",
    "CountQuery",
    "EdgeListGraphView",
    "GraphQuery",
    "GraphView",
    "GraphVisualizer",
    "JsonPart",
    "NodeListQuery",
    "NodesPart",
    "RelationshipListQuery",
    "RelationshipsPart",
    "StandardGraphView",
    "clean",
    "count_of",
    "notice_of",
]
