"""
------------------------------------------------------------------------
File : service.py
Description: AnalysisService - applies an analysis to the graph of an
             "ekg" object (the legacy process_analysis and
             execute_rollback_data of Services/filters_service.py) as a
             compensating action (scheda C26):
             1. the configuration is saved in the legacy format in
                <root dataset>/Analyses/<name>.json (409 if the name is
                taken, like check_unique_analysis_name), with "based_on"
                when the parent is an analysis;
             2. on the loaded graph of the parent (ekg's derive_state, the
                memgraph tool's advance): the counts of nodes and
                relationships, "analysis.before_apply" (other packages
                remove what the filters would leave stale - their
                subscriptions are critical, an error cancels the
                analysis), the filters in their order, the counts again;
             3. if anything fails: the graph of the parent is rebuilt
                (derive_state), the file is removed, the error re-raised,
                and no object is created. If nothing changed the analysis
                is still created, marked "unchanged" (the legacy code
                answered "Nothing changed" and kept the file).
             apply_filters() is shared with the state provider, which
             replays an analysis after a rebuild of the parent.
             AnalysisRuntime is what the operations, the provider and the
             exporter need of the active package: the filters contributed
             by every package and the EventBus.
Project : soup-packages/ekg_analysis
------------------------------------------------------------------------
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import soup_pkg_ekg.api as ekg
from soup_pkg_ekg.api import Query
from soup_pkg_ekg_views.api import count_of

from soup.core.contracts import ConflictError, ObjectRef, PluginContext, ToolAccess

from .analysis import Analysis, analysis_file, is_analysis
from .filters import AnalysisFilter, FilterContext, Run

_LOGGER = logging.getLogger("soup.ekg_analysis")

ANALYSIS_FILTERS_POINT = "ekg.analysis_filters"
# Published before the filters of an analysis run on the loaded graph of
# its parent. Payload: {"object": id of the parent, "analysis": name,
# "spec": Analysis.to_spec()}.
ANALYSIS_BEFORE_APPLY = "analysis.before_apply"

STORAGE = "storage"

_COUNT_NODES = Query("MATCH (n) RETURN count(n) AS count")
_COUNT_RELATIONSHIPS = Query("MATCH ()-[r]->() RETURN count(r) AS count")


class AnalysisRuntime:
    def __init__(self, ctx: PluginContext):
        self._ctx = ctx

    def filters(self) -> list[AnalysisFilter]:
        """The filters contributed by every active package, by `order` then registration (first of each key)."""

        found: dict[str, AnalysisFilter] = {}
        for item in self._ctx.contributions(ANALYSIS_FILTERS_POINT):
            key = getattr(item, "key", "")
            if key and key not in found:
                found[key] = item
        return sorted(found.values(), key=lambda item: item.order)

    def publish(self, event: str, payload: Mapping[str, Any]) -> None:
        self._ctx.publish(event, payload)


def graph_counts(run: Run) -> dict[str, int]:
    """get_node_and_relationship_count."""

    return {"nodes": count_of(run(_COUNT_NODES)), "relationships": count_of(run(_COUNT_RELATIONSHIPS))}


def apply_filters(conditions: Sequence[tuple[AnalysisFilter, Mapping[str, Any]]], run: Run) -> None:
    ctx = FilterContext(run)
    for item, condition in conditions:
        for query in item.to_queries(condition, ctx):
            run(query)


@dataclass(frozen=True)
class AppliedAnalysis:
    dataset: str
    graph_key: str
    before: dict[str, int]
    after: dict[str, int]
    based_on: str | None = None

    @property
    def changed(self) -> bool:
        return self.before != self.after


class AnalysisService:
    def __init__(self, runtime: AnalysisRuntime):
        self._runtime = runtime

    def apply(self, parent: ObjectRef, analysis: Analysis, tools: ToolAccess) -> AppliedAnalysis:
        """
        :raises ConflictError: an analysis with this name already exists for the dataset
        :raises ServiceUnavailableError: a filter of the analysis is not active
        """

        conditions = analysis.ordered(self._runtime.filters())
        dataset = ekg.root_of(parent).meta["dataset"]
        repository = ekg.DatasetRepository(tools.get(STORAGE))
        if analysis.name in repository.analyses(dataset):
            raise ConflictError(f"Analysis '{analysis.name}' already exists for the dataset '{dataset}'")
        # A nested analysis names its parent in the file, so the adoption
        # rebuilds the chain from the files alone.
        found = analysis_file(parent) if is_analysis(parent) else None
        based_on = found[1] if found else None
        repository.save_analysis(dataset, analysis.name, analysis.to_legacy(dataset, based_on))

        counts: dict[str, dict[str, int]] = {}

        def mutate(run: Run) -> None:
            counts["before"] = graph_counts(run)
            self._runtime.publish(ANALYSIS_BEFORE_APPLY, {"object": parent.id, "analysis": analysis.name,
                                                          "spec": analysis.to_spec()})
            apply_filters(conditions, run)
            counts["after"] = graph_counts(run)

        try:
            graph_key = ekg.derive_state(parent, mutate, tools)
        except Exception:
            remove_file(repository, dataset, analysis.name)
            raise
        return AppliedAnalysis(dataset, graph_key, counts["before"], counts["after"], based_on)


def remove_file(repository: Any, dataset: str, name: str) -> None:
    try:
        repository.delete_analysis(dataset, name)
    except Exception:  # noqa: BLE001 - the original error (if any) is the one to report
        _LOGGER.exception("The file of the analysis '%s' of '%s' could not be removed", name, dataset)
