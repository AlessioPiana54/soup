"""
------------------------------------------------------------------------
File : plugin.py
Description: CsvReaderPlugin - registers CsvEventLogReader as the
             "csv" input reader.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from soup.core.contracts import PluginContext, SoupPlugin
from soup.plugins.csv_reader.reader import CsvEventLogReader


class CsvReaderPlugin(SoupPlugin):
    name = "csv_reader"
    version = "1.0.0"
    api_version = "2.0"

    def register(self, ctx: PluginContext) -> None:
        ctx.add_input_reader(CsvEventLogReader.format_id, CsvEventLogReader())
