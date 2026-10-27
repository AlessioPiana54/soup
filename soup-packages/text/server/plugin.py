"""
------------------------------------------------------------------------
File : plugin.py
Description: Plugin - registers the text importer, visualizer and
             exporter. The importer and the visualizer share one cache of
             the decoded files, created here for this plugin instance (a
             disable/enable builds a new instance with an empty cache)
             with the limits of SOUP_TEXT_CACHE_OBJECTS and
             SOUP_TEXT_CACHE_MB (default 8 objects, 200 MB). Name, version
             and dependencies come from soup-package.json.
Project : soup-packages/text
------------------------------------------------------------------------
"""

from __future__ import annotations

import os
from typing import Optional

from soup.core.contracts import PluginContext, SoupPlugin

from .cache import ParsedCache, limits_from_env
from .text import OriginalFileExporter, TextFile, TextImporter, TextVisualizer, new_cache

ENV_PREFIX = "SOUP_TEXT"


class Plugin(SoupPlugin):
    cache: Optional[ParsedCache[TextFile]] = None

    def register(self, ctx: PluginContext) -> None:
        max_objects, max_bytes = limits_from_env(os.environ, ENV_PREFIX)
        self.cache = cache = new_cache(max_objects, max_bytes)
        ctx.add_importer(TextImporter(cache))
        ctx.add_visualizer(TextVisualizer(cache))
        ctx.add_exporter(OriginalFileExporter())

    def on_shutdown(self, ctx: PluginContext) -> None:
        if self.cache is not None:
            self.cache.clear()
