"""
------------------------------------------------------------------------
File : fakes.py
Description: In-memory fake implementations of the GraphDatabase and
             FileStorage ports, used by tests instead of the real
             Memgraph/Docker adapters (soup/infrastructure/*).
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from typing import Any

from soup.core.contracts import FileStorage, GraphDatabase, Query


class InMemoryFileStorage(FileStorage):
    """FileStorage fake backed by a plain dict - no filesystem/Docker I/O."""

    def __init__(self) -> None:
        self._files: dict[str, bytes] = {}

    def read(self, path: str) -> bytes:
        if path not in self._files:
            raise FileNotFoundError(path)
        return self._files[path]

    def write(self, path: str, data: bytes) -> None:
        self._files[path] = bytes(data)

    def exists(self, path: str) -> bool:
        return path in self._files

    def delete(self, path: str) -> None:
        self._files.pop(path, None)

    def list(self, prefix: str = "") -> list[str]:
        return sorted(path for path in self._files if path.startswith(prefix))


class FakeDatabase(GraphDatabase):
    """
    GraphDatabase fake that records every Query it receives (text and
    params, in order) and returns a configurable canned response per
    query text, falling back to a default response.
    """

    def __init__(self) -> None:
        self.received_queries: list[Query] = []
        self._responses: dict[str, list[dict[str, Any]]] = {}
        self._default_response: list[dict[str, Any]] = []

    def set_response(self, query_text: str, rows: list[dict[str, Any]]) -> None:
        self._responses[query_text] = rows

    def set_default_response(self, rows: list[dict[str, Any]]) -> None:
        self._default_response = rows

    def run(self, query: Query) -> list[dict[str, Any]]:
        self.received_queries.append(query)
        return self._responses.get(query.text, self._default_response)
