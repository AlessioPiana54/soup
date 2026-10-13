"""
------------------------------------------------------------------------
File : plugin.py
Description: CausalDfPlugin - registers CausalDirectlyFollowsStep as a
             build step.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from soup.core.contracts import PluginContext, SoupPlugin
from soup.plugins.causal_df.step import CausalDirectlyFollowsStep


class CausalDfPlugin(SoupPlugin):
    name = "causal_df"
    version = "1.0.0"

    def register(self, ctx: PluginContext) -> None:
        ctx.add_build_step(CausalDirectlyFollowsStep.key, CausalDirectlyFollowsStep())
