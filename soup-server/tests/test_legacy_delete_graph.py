"""
------------------------------------------------------------------------
File : test_legacy_delete_graph.py
Description: The legacy DELETE of the standard graph (served under
             /api/v2 until commit 11) checks the deletion of the :Entity
             and of the :Event nodes each with its own count: before
             commit 10 it read ['count'] from queries returning
             entity_count and node_count, so it never answered 200.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from flask import Flask


class _Connector:
    """The legacy database connector, answering the two verification counts."""

    def __init__(self, entities: int, events: int):
        self.counts = {"entity_count": entities, "node_count": events}
        self.queries: list[str] = []

    def connect(self) -> None:
        return None

    def close(self) -> None:
        return None

    def run_query_memgraph(self, query: str):
        self.queries.append(query)
        for column in self.counts:
            if f"as {column}" in query:
                return [{column: self.counts[column]}]
        return []


def _delete(connector):
    from Services.Graph.op_graph_service import OperationGraphService

    with Flask(__name__).app_context():
        response, status = OperationGraphService.delete_graph_s(connector)
    return status, response.get_json()


def test_the_deletion_is_verified_with_the_count_of_each_label():
    assert _delete(_Connector(entities=0, events=0))[0] == 200
    assert _delete(_Connector(entities=2, events=0))[0] == 404
    assert _delete(_Connector(entities=0, events=3))[0] == 404
