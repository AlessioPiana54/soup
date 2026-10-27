"""
------------------------------------------------------------------------
File : api.py
Description: Public API of the ekg_analysis package. Other packages
             import it as soup_pkg_ekg_analysis.api, and only if they list
             "ekg_analysis" in their `requires`:
             - ANALYSIS_FILTERS_POINT ("ekg.analysis_filters"): an
               AnalysisFilter (or an EntityConditionFilter) contributed
               with ctx.contribute(ANALYSIS_FILTERS_POINT, item,
               key=item.key, order=item.order) becomes a variant of "Nuova
               analisi" and a key of the configuration files; FilterContext
               is what to_queries() may read of the graph; OPERATORS the
               closed list of the operators (with their Cypher form);
             - ANALYSIS_BEFORE_APPLY ("analysis.before_apply"): published
               on the loaded graph of the parent before the filters of a
               new analysis run, with {object: id of the parent, analysis:
               name, spec}. Subscribe as critical (ctx.subscribe(...,
               critical=True)): an error cancels the analysis and the
               graph of the parent is rebuilt. A package that only reacts
               to the event (e.g. ekg_class_graph) does not need to
               require ekg_analysis: the name is enough;
             - Analysis, the model of an analysis, and ANALYSIS_PROVIDER,
               the meta.state provider of the objects of an analysis.
Project : soup-packages/ekg_analysis
------------------------------------------------------------------------
"""

from .analysis import ANALYSIS_PROVIDER, Analysis
from .filters import OPERATORS, AnalysisFilter, EntityConditionFilter, FilterContext, clean_timestamp
from .service import ANALYSIS_BEFORE_APPLY, ANALYSIS_FILTERS_POINT

__all__ = [
    "ANALYSIS_BEFORE_APPLY",
    "ANALYSIS_FILTERS_POINT",
    "ANALYSIS_PROVIDER",
    "OPERATORS",
    "Analysis",
    "AnalysisFilter",
    "EntityConditionFilter",
    "FilterContext",
    "clean_timestamp",
]
