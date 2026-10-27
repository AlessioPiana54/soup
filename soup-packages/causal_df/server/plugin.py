"""
------------------------------------------------------------------------
File : plugin.py
Description: Plugin - contributes CausalDirectlyFollowsStep to the ekg
             package's "ekg.build_steps" extension point, with its order
             (450). Name, version, api_version and dependencies come from
             soup-package.json.
Project : soup-packages/causal_df
------------------------------------------------------------------------
"""

from __future__ import annotations

from soup.core.contracts import PluginContext, SoupPlugin
from soup_pkg_ekg.api import BUILD_STEPS_POINT

from .step import CausalDirectlyFollowsStep


class Plugin(SoupPlugin):
    def register(self, ctx: PluginContext) -> None:
        step = CausalDirectlyFollowsStep()
        ctx.contribute(BUILD_STEPS_POINT, step, key=step.key, order=step.order)
