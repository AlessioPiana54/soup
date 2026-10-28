"""
------------------------------------------------------------------------
File : build.py
Description: EkgBuildStep - one step of the EKG build pipeline - and
             BuildContext, the data threaded through it (moved here from
             soup/core/contracts/build.py; scheda C13). The package's own
             steps (steps.py) and the steps other packages contribute to
             the "ekg.build_steps" extension point (e.g. causal_df, order
             450) both implement EkgBuildStep; EkgService orders them by
             `order` without knowing which package contributed which step.
Project : soup-packages/ekg
------------------------------------------------------------------------
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from soup_pkg_tool_memgraph.api import GraphDatabase


@dataclass
class BuildContext:
    """
    Mutable context threaded through the build pipeline for one dataset.

    `mapping` is the resolved ColumnMapping (event_log.py) - typed as Any
    here so a step contributed by another package needs nothing but this
    module (through api.py) to implement the contract.

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
    """
    One step of the EKG build pipeline (this package's or contributed to
    "ekg.build_steps"). `phase` groups the steps for the process times
    of the dataset config (see ekg_service.PHASE_TIMES).
    """

    key: str
    order: int
    phase: str = ""

    def applies(self, ctx: BuildContext) -> bool:
        """Whether this step runs at all for the current build. Default: always."""

        return True

    @abstractmethod
    def execute(self, ctx: BuildContext, db: GraphDatabase) -> None:
        raise NotImplementedError
