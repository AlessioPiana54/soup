"""
------------------------------------------------------------------------
File : api.py
Description: Public API of the ekg package. Other packages import it as
             soup_pkg_ekg.api, and only if they list "ekg" in their
             `requires`:
             - the event log: Table (and the pandas conversions),
               EventLogData, ColumnMapping, EventLog;
             - build_ekg(obj, data, mapping, tools, ...): stage and build
               the EKG of an object being created; ensure_loaded(obj,
               tools, force=False), dispose(obj, tools) and
               graph_key_of(obj), the memgraph tool state of its graph;
             - the extension points: BUILD_STEPS_POINT (EkgBuildStep,
               BuildContext) and STATE_PROVIDERS_POINT (StateProvider);
             - the events EKG_BEFORE_RESET and EKG_BUILT, the kind
               EKG_KIND, and Query/ident to write the Cypher of a step.
             The callers of build_ekg/ensure_loaded/dispose pass their own
             tools and must declare "memgraph" and "storage".
Project : soup-packages/ekg
------------------------------------------------------------------------
"""

from soup_pkg_tool_memgraph.api import Query, ident

from .adoption import LEGACY_IMPORTER, LEGACY_PACKAGE
from .build import BuildContext, EkgBuildStep
from .builder import EKG_BEFORE_RESET, EKG_BUILT, EKG_KIND, build_ekg
from .event_log import ColumnMapping, EventLog, EventLogData
from .runtime import BUILD_STEPS_POINT, STATE_PROVIDERS_POINT
from .state import StateProvider, dispose, ensure_loaded, graph_key_of, is_derived
from .tables import Table, from_dataframe, to_dataframe

__all__ = [
    "BUILD_STEPS_POINT",
    "EKG_BEFORE_RESET",
    "EKG_BUILT",
    "EKG_KIND",
    "LEGACY_IMPORTER",
    "LEGACY_PACKAGE",
    "STATE_PROVIDERS_POINT",
    "BuildContext",
    "ColumnMapping",
    "EkgBuildStep",
    "EventLog",
    "EventLogData",
    "Query",
    "StateProvider",
    "Table",
    "build_ekg",
    "dispose",
    "ensure_loaded",
    "from_dataframe",
    "graph_key_of",
    "ident",
    "is_derived",
    "to_dataframe",
]
