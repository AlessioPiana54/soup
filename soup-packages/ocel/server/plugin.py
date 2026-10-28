"""
------------------------------------------------------------------------
File : plugin.py
Description: Plugin - registers the two importers of OCEL 2.0 JSON files
             (as tables, as an EKG), the two visualizers and the exporter
             of "ocel_tables" objects and the "Scomponi in EKG"
             operation. The contributions that read the tables share one
             cache, created here for this plugin instance (a
             disable/enable builds a new instance with an empty cache)
             with the limits of SOUP_OCEL_CACHE_OBJECTS and
             SOUP_OCEL_CACHE_MB (default 8 objects, 200 MB). Name, version
             and dependencies come from soup-package.json.
Project : soup-packages/ocel
------------------------------------------------------------------------
"""

from __future__ import annotations

import os

from soup_pkg_soup_base.api import ParsedCache, limits_from_env

from soup.core.contracts import PluginContext, SoupPlugin

from .graph import DecomposeToEkg, OcelEkgImporter
from .store import OcelTables
from .tables import OcelJsonExporter, OcelSummaryVisualizer, OcelTablesImporter, OcelTablesVisualizer
from .tables_cache import new_cache

ENV_PREFIX = "SOUP_OCEL"


class Plugin(SoupPlugin):
    cache: ParsedCache[OcelTables] | None = None

    def register(self, ctx: PluginContext) -> None:
        max_objects, max_bytes = limits_from_env(os.environ, ENV_PREFIX)
        self.cache = cache = new_cache(max_objects, max_bytes)
        ctx.add_importer(OcelTablesImporter(cache))
        ctx.add_importer(OcelEkgImporter())
        ctx.add_visualizer(OcelTablesVisualizer(cache))
        ctx.add_visualizer(OcelSummaryVisualizer())
        ctx.add_operation(DecomposeToEkg(cache))
        ctx.add_exporter(OcelJsonExporter(cache))

    def on_shutdown(self, ctx: PluginContext) -> None:
        if self.cache is not None:
            self.cache.clear()
