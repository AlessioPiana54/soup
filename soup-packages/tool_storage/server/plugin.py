"""
------------------------------------------------------------------------
File : plugin.py
Description: Plugin - registers the "storage", "catalog" and
             "preferences" tools on one backend (Docker volume or local
             folder) configured from the environment.
Project : soup-packages/tool_storage
------------------------------------------------------------------------
"""

from __future__ import annotations

import os

from soup.core.contracts import PluginContext, SoupPlugin

from .catalog import FileCatalog
from .config import StorageConfig, build_backend
from .preferences import FilePreferences
from .storage import StorageTool


class Plugin(SoupPlugin):
    def register(self, ctx: PluginContext) -> None:
        config = StorageConfig.from_env(os.environ)
        backend = build_backend(config)
        ctx.add_tool(StorageTool(backend, root=config.root))
        ctx.add_tool(FileCatalog(backend))
        ctx.add_tool(FilePreferences(backend))
