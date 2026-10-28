"""
------------------------------------------------------------------------
File : port.py
Description: GraphDatabase, the port of the graph store: run a
             parameterized Query and get the rows back. The "memgraph"
             tool (tool.py) is one, on top of the neo4j driver
             (database.py); the packages that write Cypher (ekg and the
             ones requiring it) type their database with it. Depends only
             on the Query value object.
Project : soup-packages/tool_memgraph
------------------------------------------------------------------------
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .query import Query


class GraphDatabase(ABC):
    """Port for running parameterized Cypher queries against the graph store."""

    @abstractmethod
    def run(self, query: Query) -> list[dict[str, Any]]:
        """Execute `query` and return the result rows as a list of dicts."""
        raise NotImplementedError
