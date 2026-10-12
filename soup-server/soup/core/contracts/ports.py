"""
------------------------------------------------------------------------
File : ports.py
Description: Stable ports (abstract interfaces) between the core and the
             infrastructure adapters that implement them
             (soup/infrastructure). Depends only on the Query value
             object - no pandas, no neo4j driver, no Docker SDK, no Flask.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from soup.core.contracts.query import Query


class GraphDatabase(ABC):
    """Port for running parameterized Cypher queries against the graph store."""

    @abstractmethod
    def run(self, query: Query) -> list[dict[str, Any]]:
        """Execute `query` and return the result rows as a list of dicts."""
        raise NotImplementedError


class FileStorage(ABC):
    """Port for reading/writing dataset files, independent of where they live."""

    @abstractmethod
    def read(self, path: str) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def write(self, path: str, data: bytes) -> None:
        raise NotImplementedError

    @abstractmethod
    def exists(self, path: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def delete(self, path: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def list(self, prefix: str = "") -> list[str]:
        raise NotImplementedError
