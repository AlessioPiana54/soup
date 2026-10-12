"""
------------------------------------------------------------------------
File : memgraph.py
Description: GraphDatabase adapter for Memgraph. Connection parameters
             and the session.run(...) call are taken as-is from
             Models/memgraph_connector_model.py (not modified by this
             session), but instead of a connect()/close() pair opened and
             closed on every request, this adapter keeps a single driver
             per process: created lazily on first use, thread-safe to
             create (double-checked locking), and closed only when the
             engine shuts down.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import threading
from typing import Any, Optional

from neo4j import GraphDatabase as Neo4jGraphDatabase

from soup.core.contracts import GraphDatabase as GraphDatabasePort
from soup.core.contracts import Query


class MemgraphDatabase(GraphDatabasePort):
    def __init__(self, uri: str, auth: tuple = ("", "")):
        self._uri = uri
        self._auth = auth
        self._driver = None
        self._lock = threading.Lock()

    def _get_driver(self):
        if self._driver is None:
            with self._lock:
                if self._driver is None:
                    self._driver = Neo4jGraphDatabase.driver(self._uri, auth=self._auth)
        return self._driver

    def run(self, query: Query) -> list[dict[str, Any]]:
        driver = self._get_driver()
        with driver.session() as session:
            result = session.run(query.text, query.params, database="memgraph", metrics=True)
            return [record.data() for record in result]

    def close(self) -> None:
        with self._lock:
            if self._driver is not None:
                self._driver.close()
                self._driver = None
