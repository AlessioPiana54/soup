"""
------------------------------------------------------------------------
File : api.py
Description: Public API of the ekg_views package. Other packages import it
             as soup_pkg_ekg_views.api, and only if they list "ekg_views"
             in their `requires`, to contribute to its extension points:
             - GRAPH_VIEWS_POINT ("ekg.graph_views"): GraphView, or
               EdgeListGraphView for the relationships of some types
               between nodes of some labels (StandardGraphView and
               ObjectGraphView are the ones of ekg_views);
             - QUERIES_POINT ("ekg.queries"): GraphQuery, or the bases
               CountQuery, NodeListQuery, RelationshipListQuery;
             - JSON_PARTS_POINT ("ekg.json_parts"): JsonPart;
             - STATS_NOTICES_POINT ("ekg.stats_notices"): StatsNotice, a
               notice of the Statistiche of an object;
             with ctx.contribute(POINT, item, key=item.key). Each item
             declares the object kinds it applies to (`kinds`, default
             ("ekg",); STANDARD_KINDS for the ones of ekg_views).
             GraphVisualizer is the "Grafo" visualizer, to subclass for
             the objects of another kind with its own element. clean()
             makes the values read from Memgraph JSON-ready.
             NullEntities is the query of the event properties with null
             values and warning_label() the warning shown for them, for
             the forms that offer entity types (ekg_class_graph).
Project : soup-packages/ekg_views
------------------------------------------------------------------------
"""

from .builtin_queries import NullEntities
from .contributions import (
    GRAPH_VIEWS_POINT,
    JSON_PARTS_POINT,
    QUERIES_POINT,
    STATS_NOTICES_POINT,
    GraphVisualizer,
    StatsNotice,
    notice_of,
    warning_label,
)
from .json_parts import JsonPart, NodesPart, RelationshipsPart, RelPart
from .kinds import DEFAULT_KINDS, STANDARD_KINDS
from .queries import CountQuery, GraphQuery, NodeListQuery, RelationshipListQuery, count_of
from .values import clean
from .views import EdgeListGraphView, GraphView, ObjectGraphView, StandardGraphView

__all__ = [
    "DEFAULT_KINDS",
    "GRAPH_VIEWS_POINT",
    "JSON_PARTS_POINT",
    "QUERIES_POINT",
    "STANDARD_KINDS",
    "STATS_NOTICES_POINT",
    "CountQuery",
    "EdgeListGraphView",
    "GraphQuery",
    "GraphView",
    "GraphVisualizer",
    "JsonPart",
    "NodeListQuery",
    "NullEntities",
    "NodesPart",
    "ObjectGraphView",
    "RelPart",
    "RelationshipListQuery",
    "RelationshipsPart",
    "StandardGraphView",
    "StatsNotice",
    "clean",
    "count_of",
    "notice_of",
    "warning_label",
]
