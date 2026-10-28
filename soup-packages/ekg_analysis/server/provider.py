"""
------------------------------------------------------------------------
File : provider.py
Description: AnalysisStateProvider ("analysis"), contributed to
             "ekg.state_providers": when ekg's ensure_loaded rebuilds the
             graph of an analysis (another object was opened meanwhile),
             it replays meta.state.spec - the filters only, in their
             order, on the graph of the parent just rebuilt (no counts and
             no "analysis.before_apply": nothing of the old graph is left
             after a rebuild). A filter of the analysis that no active
             package contributes is a 503.
Project : soup-packages/ekg_analysis
------------------------------------------------------------------------
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import soup_pkg_ekg.api as ekg
from soup_pkg_ekg.api import GraphDatabase

from .analysis import ANALYSIS_PROVIDER, Analysis
from .filters import AnalysisFilter
from .service import apply_filters


class AnalysisStateProvider(ekg.StateProvider):
    key = ANALYSIS_PROVIDER

    def __init__(self, filters: Callable[[], list[AnalysisFilter]]):
        self._filters = filters

    def apply(self, spec: Mapping[str, Any], db: GraphDatabase) -> None:
        apply_filters(Analysis.from_spec(spec).ordered(self._filters()), db.run)
