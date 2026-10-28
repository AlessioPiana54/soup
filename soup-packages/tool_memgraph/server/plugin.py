"""
------------------------------------------------------------------------
File : plugin.py
Description: Plugin - registers the "memgraph" tool on a single
             MemgraphDatabase (driver created on first use) configured
             from the environment, and closes the driver on shutdown or
             when the package is disabled.
Project : soup-packages/tool_memgraph
------------------------------------------------------------------------
"""

from __future__ import annotations

import os

from soup.core.contracts import PluginContext, SoupPlugin

from .config import MemgraphConfig
from .database import MemgraphDatabase
from .tool import MemgraphTool


class Plugin(SoupPlugin):
    def __init__(self) -> None:
        self._tool: MemgraphTool | None = None

    def register(self, ctx: PluginContext) -> None:
        config = MemgraphConfig.from_env(os.environ)
        self._tool = MemgraphTool(MemgraphDatabase(uri=config.uri, auth=("", "")))
        ctx.add_tool(self._tool)

    def on_shutdown(self, ctx: PluginContext) -> None:
        if self._tool is not None:
            self._tool.close()
            self._tool = None
