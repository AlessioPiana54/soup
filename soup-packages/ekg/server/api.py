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
               derive_state(parent, mutate, tools), the graph of a new
               derived object made on the loaded parent; root_of(obj),
               its root "ekg" object; new_graph_key();
             - DatasetRepository: the files of a dataset, the analyses
               in Analyses/ included;
             - the extension points: BUILD_STEPS_POINT (EkgBuildStep,
               BuildContext) and STATE_PROVIDERS_POINT (StateProvider);
             - the events EKG_BEFORE_RESET and EKG_BUILT, the kind
               EKG_KIND, and GraphDatabase and Query/ident to write the Cypher
               of a step.
             The callers pass their own tools: build_ekg needs "memgraph"
             and "storage", ensure_loaded, derive_state and dispose only
             "memgraph" (the datasets are read with this package's own
             storage).
Project : soup-packages/ekg
------------------------------------------------------------------------
"""

from soup_pkg_tool_memgraph.api import GraphDatabase, Query, ident

from .adoption import LEGACY_IMPORTER, LEGACY_PACKAGE
from .build import BuildContext, EkgBuildStep
from .builder import EKG_BEFORE_RESET, EKG_BUILT, EKG_KIND, build_ekg, new_graph_key
from .dataset_repository import ANALYSES_FOLDER, DatasetRepository
from .event_log import ColumnMapping, EventLog, EventLogData
from .runtime import BUILD_STEPS_POINT, STATE_PROVIDERS_POINT
from .state import StateProvider, derive_state, dispose, ensure_loaded, graph_key_of, is_derived, root_of
from .tables import Table, from_dataframe, to_dataframe

__all__ = [
    "ANALYSES_FOLDER",
    "BUILD_STEPS_POINT",
    "EKG_BEFORE_RESET",
    "EKG_BUILT",
    "EKG_KIND",
    "LEGACY_IMPORTER",
    "LEGACY_PACKAGE",
    "STATE_PROVIDERS_POINT",
    "BuildContext",
    "ColumnMapping",
    "DatasetRepository",
    "EkgBuildStep",
    "GraphDatabase",
    "EventLog",
    "EventLogData",
    "Query",
    "StateProvider",
    "Table",
    "build_ekg",
    "derive_state",
    "dispose",
    "ensure_loaded",
    "from_dataframe",
    "graph_key_of",
    "ident",
    "is_derived",
    "new_graph_key",
    "root_of",
    "to_dataframe",
]
