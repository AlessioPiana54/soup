"""
------------------------------------------------------------------------
File : plugin.py
Description: Plugin - registers the template's importer, visualizer and
             operation.
             Name, version, api_version and dependencies come from
             soup-package.json.
Project : soup-packages/_template
------------------------------------------------------------------------
"""

from __future__ import annotations

from soup.core.contracts import PluginContext, SoupPlugin

from .text import StatsReport, TextImporter, TextVisualizer


class Plugin(SoupPlugin):
    def register(self, ctx: PluginContext) -> None:
        ctx.add_importer(TextImporter())
        ctx.add_visualizer(TextVisualizer())
        ctx.add_operation(StatsReport())
