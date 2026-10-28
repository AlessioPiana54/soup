"""
------------------------------------------------------------------------
File : step.py
Description: CausalDirectlyFollowsStep - inserted between CorrelationStep
             (400) and the ekg package's DirectlyFollowsStep (500). Only applies
             when the build context carries trigger/target pairs
             (ctx.trigger_target_rows, from the request's trigger_N/
             target_N form fields); for each pair it runs the causal
             queries (cypher.py) and marks both entity types as handled
             in ctx.df_handled_types, so DirectlyFollowsStep skips them
             instead of creating a conflicting, non-causal :DF edge for
             the same type.
Project : soup-packages/causal_df
------------------------------------------------------------------------
"""

from __future__ import annotations

from soup_pkg_ekg.api import BuildContext, EkgBuildStep, GraphDatabase

from .cypher import reveal_causal_relationships_queries


class CausalDirectlyFollowsStep(EkgBuildStep):
    key = "causal_directly_follows"
    order = 450
    phase = "df"

    def applies(self, ctx: BuildContext) -> bool:
        return bool(ctx.trigger_target_rows)

    def execute(self, ctx: BuildContext, db: GraphDatabase) -> None:
        for pair in ctx.trigger_target_rows:
            trigger = pair["trigger"]
            target = pair["target"]

            for query in reveal_causal_relationships_queries(trigger, target):
                db.run(query)

            ctx.df_handled_types.add(trigger)
            ctx.df_handled_types.add(target)
