"""
------------------------------------------------------------------------
File : plugin.py
Description: Plugin - registers CausalDirectlyFollowsStep as a build
             step. Name, version, api_version and dependencies come from
             soup-package.json.
Project : soup-packages/causal_df
------------------------------------------------------------------------
"""

from __future__ import annotations

from soup.core.contracts import PluginContext, SoupPlugin

from .step import CausalDirectlyFollowsStep


class Plugin(SoupPlugin):
    def register(self, ctx: PluginContext) -> None:
        ctx.add_build_step(CausalDirectlyFollowsStep.key, CausalDirectlyFollowsStep())
