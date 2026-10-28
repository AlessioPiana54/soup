"""
------------------------------------------------------------------------
File : plugin.py
Description: Plugin - registers the CSV table importer, its two
             visualizers, the column distribution operation and the CSV
             exporter. They share one cache of the parsed tables, created
             here for this plugin instance (a disable/enable builds a new
             instance with an empty cache) with the limits of
             SOUP_CSV_TABLE_CACHE_OBJECTS and SOUP_CSV_TABLE_CACHE_MB
             (default 8 objects, 200 MB). Name, version and dependencies
             come from soup-package.json.
Project : soup-packages/csv_table
------------------------------------------------------------------------
"""

from __future__ import annotations

import os

from soup_pkg_soup_base.api import ParsedCache, limits_from_env

from soup.core.contracts import PluginContext, SoupPlugin

from .contributions import (
    ColumnDistribution,
    CsvExporter,
    CsvProfileVisualizer,
    CsvTableImporter,
    CsvTableVisualizer,
    Parsed,
    new_cache,
)

ENV_PREFIX = "SOUP_CSV_TABLE"


class Plugin(SoupPlugin):
    cache: ParsedCache[Parsed] | None = None

    def register(self, ctx: PluginContext) -> None:
        max_objects, max_bytes = limits_from_env(os.environ, ENV_PREFIX)
        self.cache = cache = new_cache(max_objects, max_bytes)
        ctx.add_importer(CsvTableImporter(cache))
        ctx.add_visualizer(CsvTableVisualizer(cache))
        ctx.add_visualizer(CsvProfileVisualizer(cache))
        ctx.add_operation(ColumnDistribution(cache))
        ctx.add_exporter(CsvExporter(cache))

    def on_shutdown(self, ctx: PluginContext) -> None:
        if self.cache is not None:
            self.cache.clear()
