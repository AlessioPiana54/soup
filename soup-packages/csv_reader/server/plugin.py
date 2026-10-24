"""
------------------------------------------------------------------------
File : plugin.py
Description: Plugin - registers CsvEventLogReader as the "csv" input
             reader. Name, version, api_version and dependencies come
             from soup-package.json.
Project : soup-packages/csv_reader
------------------------------------------------------------------------
"""

from __future__ import annotations

from soup.core.contracts import PluginContext, SoupPlugin

from .reader import CsvEventLogReader


class Plugin(SoupPlugin):
    def register(self, ctx: PluginContext) -> None:
        ctx.add_input_reader(CsvEventLogReader.format_id, CsvEventLogReader())
