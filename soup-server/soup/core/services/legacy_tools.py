"""
------------------------------------------------------------------------
File : legacy_tools.py
Description: How the legacy import path (/api/v2/graph: DatasetRepository,
             EkgService, EventLogHandler) reaches the "memgraph" and
             "storage" tools, now provided by the tool_memgraph and
             tool_storage packages. ToolGraph and ToolStorage resolve the
             tool on every call, so disabling/enabling the providing
             package at runtime takes effect immediately, and a missing
             tool answers 503 instead of failing at startup. The core
             does not import the packages: it reaches the tools by name,
             checking the GraphDatabase port (memgraph) or the methods it
             calls (storage).
             TODO(commit 8): the legacy path moves to the ekg package,
             which declares both tools in requires_tools; this module goes.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from typing import Any, Protocol

from soup.core.contracts import FileStorage, GraphDatabase, Query, ServiceUnavailableError


class StorageSpaceTool(Protocol):
    """What the legacy path uses of the "storage" tool."""

    def space(self, namespace: str) -> FileStorage:
        ...

    def path_for(self, namespace: str, name: str) -> str:
        ...

    def delete_space(self, namespace: str) -> None:
        ...


class ToolGraph(GraphDatabase):
    """GraphDatabase that forwards to the "memgraph" tool (CoreTools.graph())."""

    def __init__(self, core_tools: Any):
        self._core_tools = core_tools

    def run(self, query: Query) -> list[dict[str, Any]]:
        return self._core_tools.graph().run(query)

    def invalidate(self) -> None:
        """The legacy path writes outside ensure_loaded: forget the tool's active state."""

        try:
            tool = self._core_tools.graph()
        except ServiceUnavailableError:
            return  # no tool, no state to forget
        invalidate = getattr(tool, "invalidate", None)
        if callable(invalidate):
            invalidate()


class ToolStorage:
    """StorageSpaceTool that forwards to the "storage" tool (CoreTools.storage())."""

    def __init__(self, core_tools: Any):
        self._core_tools = core_tools

    def space(self, namespace: str) -> FileStorage:
        return self._core_tools.storage().space(namespace)

    def path_for(self, namespace: str, name: str) -> str:
        return self._core_tools.storage().path_for(namespace, name)

    def delete_space(self, namespace: str) -> None:
        self._core_tools.storage().delete_space(namespace)
