"""
------------------------------------------------------------------------
File : build.py
Description: EkgBuildStep - one step of the EKG build pipeline - and
             BuildContext, the data threaded through it. Core steps
             (soup/core/ekg/steps.py) and plugin steps
             (soup-packages/causal_df) both implement EkgBuildStep; the
             core discovers and orders them without knowing which plugin
             contributed which step (see soup/core/services/ekg_service.py).
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from soup.core.contracts.ports import GraphDatabase


@dataclass
class BuildContext:
    """
    Mutable context threaded through the build pipeline for one dataset.

    `mapping` is the resolved ColumnMapping (soup.core.event_log) - typed
    as Any here so this contract does not need to import soup/core/
    event_log.py (contracts depend on nothing); steps that need it import
    ColumnMapping themselves for type-checking purposes only.

    `df_handled_types` lets an earlier step (e.g. causal_df's
    CausalDirectlyFollowsStep) declare which entity types it has already
    created :DF edges for, so DirectlyFollowsStep (order 500) skips them
    instead of creating duplicate/conflicting edges for the same type.
    """

    dataset_name: str
    mapping: Any
    events_csv_path: str
    entities_csv_path: str
    trigger_target_rows: tuple = ()
    df_handled_types: set = field(default_factory=set)


class EkgBuildStep(ABC):
    """One step of the EKG build pipeline (core- or plugin-contributed)."""

    key: str
    order: int
    phase: str = ""

    def applies(self, ctx: BuildContext) -> bool:
        """Whether this step runs at all for the current build. Default: always."""

        return True

    @abstractmethod
    def execute(self, ctx: BuildContext, db: GraphDatabase) -> None:
        raise NotImplementedError
