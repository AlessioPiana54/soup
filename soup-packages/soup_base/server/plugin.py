"""
------------------------------------------------------------------------
File : plugin.py
Description: Plugin - registers the Report visualizer and the JSON
             exporter of reports. The reusable elements live in app/;
             name, version and dependencies come from soup-package.json.
Project : soup-packages/soup_base
------------------------------------------------------------------------
"""

from __future__ import annotations

from soup.core.contracts import PluginContext, SoupPlugin

from .report import ReportJsonExporter, ReportVisualizer


class Plugin(SoupPlugin):
    def register(self, ctx: PluginContext) -> None:
        ctx.add_visualizer(ReportVisualizer())
        ctx.add_exporter(ReportJsonExporter())
