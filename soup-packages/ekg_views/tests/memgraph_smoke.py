"""
------------------------------------------------------------------------
File : memgraph_smoke.py
Description: Smoke test of every query ekg_views generates, against a REAL
             Memgraph (not collected by pytest: the name does not start
             with test_). It empties the database, writes a small EKG
             (4 :Event, 3 :Entity, :CORR and :DF, the schema of the ekg
             package), then runs and transforms: the 20 GraphQuery of
             builtin_queries.py, the 4 JsonPart, and for StandardGraphView
             the edges, the max data, the node/edge search (with and
             without a node label) and the node query, for every
             combination of relationship types. It prints one line per
             query and the ones that failed, and exits with 1 if any did.

             docker run -d --rm --name ekg-views-smoke -p 17687:7687 memgraph/memgraph-mage:3.13.2
             cd soup-server
             python ../soup-packages/ekg_views/tests/memgraph_smoke.py [bolt://localhost:17687]
             docker stop ekg-views-smoke

             The database is emptied: never point it at a Memgraph with
             data you want to keep.
Project : soup-packages/ekg_views
------------------------------------------------------------------------
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path
from typing import Any, Callable

SERVER_ROOT = Path(__file__).resolve().parents[3] / "soup-server"
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from tests.packages import bundled_module  # noqa: E402

database = bundled_module("tool_memgraph", "database")
query_module = bundled_module("tool_memgraph", "query")
builtin = bundled_module("ekg_views", "builtin_queries")
parts = bundled_module("ekg_views", "json_parts")
views = bundled_module("ekg_views", "views")

Query = query_module.Query

SAMPLE_GRAPH = """
CREATE (e1:Event {Event_Id: '1', Timestamp: localDateTime('2021-01-01T10:00:00'), ActivityName: 'Create', order: 'o1', item: 'i1'}),
       (e2:Event {Event_Id: '2', Timestamp: localDateTime('2021-01-01T11:00:00'), ActivityName: 'Ship', order: 'o1', item: 'nan'}),
       (e3:Event {Event_Id: '3', Timestamp: localDateTime('2021-01-02T09:30:00'), ActivityName: 'Pay', order: 'o1', item: 'i2'}),
       (e4:Event {Event_Id: '4', Timestamp: localDateTime('2021-01-03T08:00:00'), ActivityName: 'Create', order: 'o2', item: ''}),
       (o1:Entity {Value: 'o1', Type: 'order'}), (o2:Entity {Value: 'o2', Type: 'order'}), (i1:Entity {Value: 'i1', Type: 'item'}),
       (e1)-[:CORR {Type: 'order'}]->(o1), (e2)-[:CORR {Type: 'order'}]->(o1), (e3)-[:CORR {Type: 'order'}]->(o1),
       (e4)-[:CORR {Type: 'order'}]->(o2), (e1)-[:CORR {Type: 'item'}]->(i1),
       (e1)-[:DF {Type: 'order', ID: 'o1', edge_weight: 1}]->(e2),
       (e2)-[:DF {Type: 'order', ID: 'o1', edge_weight: 1}]->(e3)
"""

# Params for the queries with fields (the others use their defaults).
PARAMS = {
    "entities_of_type": {"type": "order"},
    "events_of_activity": {"activity": "Create"},
    "df_of_type": {"entity_type": "order"},
}


def main(uri: str) -> int:
    db = database.MemgraphDatabase(uri)
    db.run(Query("MATCH (n) DETACH DELETE n"))
    db.run(Query(SAMPLE_GRAPH))

    checks: list[tuple[str, Callable[[], Any]]] = []

    for query in builtin.builtin_queries():
        def run_query(query=query):
            values = query.values(PARAMS.get(query.key, {}))
            return query.transform(db.run(query.build(values)), values)
        checks.append((f"query {query.key}", run_query))

    for part in parts.builtin_parts():
        checks.append((f"json part {part.key}", lambda part=part: part.transform(db.run(part.query()))))

    view = views.StandardGraphView()
    for relations in (["DF"], ["CORR"], ["DF", "CORR"]):
        name = "|".join(relations)
        checks.append((f"view edges {name}", lambda r=relations: view.to_graph(db.run(view.edges_query(50, r)))))
        checks.append((f"view max_data {name}", lambda r=relations: db.run(view.max_data_query(r))))
        checks.append((f"view search edge {name}", lambda r=relations: view.search_items(db.run(view.search_query("order", "edge", 0, 50, r)), "edge")))
        checks.append((f"view search edge count {name}", lambda r=relations: db.run(view.search_count_query("order", "edge", r))))
    for label in (None, "Event", "Entity"):
        checks.append((f"view search node {label}", lambda l=label: view.search_items(db.run(view.search_query("cre", "node", 0, 50, ["DF"], l)), "node")))
        checks.append((f"view search node count {label}", lambda l=label: db.run(view.search_count_query("", "node", ["DF"], l))))

    def node_query():
        [row] = db.run(Query("MATCH (n:Event {Event_Id: '1'}) RETURN id(n) AS id"))
        return view.to_node(db.run(view.node_query(row["id"])))
    checks.append(("view node", node_query))

    failures = []
    for name, check in checks:
        try:
            result = check()
        except Exception as exc:  # noqa: BLE001 - report every failure, then go on
            failures.append((name, exc))
            print(f"FAIL {name}: {exc}")
            traceback.print_exc(limit=1)
            continue
        print(f"ok   {name}: {_summary(result)}")
    db.close()

    print(f"\n{len(checks) - len(failures)}/{len(checks)} queries ok")
    for name, exc in failures:
        print(f"  failed: {name}: {exc}")
    return 1 if failures else 0


def _summary(result: Any) -> str:
    if isinstance(result, dict) and "nodes" in result:
        return f"{len(result['nodes'])} nodes, {len(result['edges'])} edges"
    if isinstance(result, list) and result and isinstance(result[0], dict) and "type" in result[0] and "data" in result[0]:
        return ", ".join(f"{block['type']}" + (f"({len(block['data']['rows'])} rows)" if block["type"] == "table" else "") for block in result)
    text = repr(result)
    return text if len(text) < 120 else text[:117] + "..."


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "bolt://localhost:17687"))
