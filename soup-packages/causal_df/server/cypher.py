"""
------------------------------------------------------------------------
File : cypher.py
Description: Parameterized rewrite of Utils/causal_query_lib.py's
             reveal_causal_rels() (not modified by this session - the
             legacy module stays in place and importable). `trigger`/
             `target` are entity-type names coming from the request's
             trigger_N/target_N form fields, so they are always bound as
             $trigger/$target rather than interpolated; 'confounder'/
             'collider' are internal, fixed constants (never derived from
             request input), so splicing them into the query text is not
             the injection risk ident()/$params guard against.
Project : soup-packages/causal_df
------------------------------------------------------------------------
"""

from __future__ import annotations

from soup_pkg_ekg.api import Query


def _find_causal_node_query(trigger: str, target: str, node_type: str) -> Query:
    direction = ">" if node_type == "collider" else "<"
    relation = node_type
    orderby = "ASC" if node_type == "collider" else "DESC"

    text = f"""
           MATCH (e:Event)-[:CORR]->(a:Entity {{Type: $trigger}})
            OPTIONAL MATCH (e)-[:CORR]->(b:Entity {{Type: $target}})
            WITH a, b, e
            ORDER BY e.Timestamp
            WITH a, b, COLLECT(e) AS event_list, MIN(toString(e.Timestamp)) AS min_timestamp
            ORDER BY min_timestamp

            WITH a.Value as a, collect([b.Value, event_list]) as b_list
            WITH a, head(b_list) AS first_trace, tail(b_list) AS remaining_traces

            UNWIND remaining_traces AS trace
            WITH a, first_trace[1] AS first_trace_events, trace[1] AS trace_event
            WITH a, first_trace_events, COLLECT(trace_event) AS remaining_events

            UNWIND first_trace_events AS fe
            UNWIND remaining_events AS trace
            WITH a, fe, remaining_events, trace[0] AS trace_event
            WITH a, fe, remaining_events, trace_event.Timestamp AS trace_timestamp
            WITH a, fe, remaining_events, COLLECT(trace_timestamp) AS remaining_timestamps
            WHERE ALL(ts IN remaining_timestamps WHERE fe.Timestamp {direction} ts)
            WITH a, fe ORDER BY fe.Timestamp {orderby}
            WITH a, collect(fe) AS fee
            WITH a, fee[0] AS {relation}_node
            SET {relation}_node.relation = '{relation}'
           """
    return Query(text, {"trigger": trigger, "target": target})


def _set_causal_rels_query(trigger: str, target: str, node_type: str) -> Query:
    direction = ">" if node_type == "collider" else "<"
    relation = node_type
    orderby = "DESC" if node_type == "collider" else "ASC"
    connection = ["<-", "-"] if node_type == "collider" else ["-", "->"]

    text = f"""
        MATCH (e:Event)-[:CORR]->(a:Entity {{Type: $trigger}})
        WHERE e.relation = '{relation}'
        MATCH (a)<-[:CORR]-(e1:Event)-[:CORR]->(b:Entity {{Type: $target}})
        WITH e, a, b, e1
        ORDER BY e1.Timestamp {orderby}
        WITH DISTINCT b, a, e1, e
        WITH b, a, collect(e1) AS event_list, e
        WHERE ALL(ev IN event_list WHERE e.Timestamp {direction} ev.Timestamp)
        WITH e, a, event_list[0] as out_{relation}
        MERGE (e){connection[0]}[:DF {{Type: a.Type, relation: 'causal'}}]{connection[1]}(out_{relation})
        """
    return Query(text, {"trigger": trigger, "target": target})


def _set_target_df_query(trigger: str, target: str) -> Query:
    text = """
            MATCH (no:Entity {Type: $trigger})<-[:CORR]-(e:Event)-[:CORR]->(n:Entity {Type: $target})
            WITH e, n, no
            ORDER BY e.Timestamp, ID(e)
            WITH n, no, collect(e) AS event_list
            UNWIND range(0, size(event_list)-2) AS i
            WITH no, n, event_list[i] AS e1, event_list[i+1] AS e2
            MERGE (e1)-[df:DF {Type: n.Type, ID: n.Value, edge_weight: 1}]->(e2)
            MERGE (e1)-[df0:DF {Type: no.Type, ID: no.Value, relation: 'causal', edge_weight: 1}]->(e2)
           """
    return Query(text, {"trigger": trigger, "target": target})


def _set_trigger_df_query(trigger: str) -> Query:
    text = """
            MATCH (e:Event)-[:CORR]->(a:Entity {Type: $trigger})
            WITH e, a
            ORDER BY e.Timestamp, ID(e)
            WITH a, collect(e) AS event_list
            UNWIND range(0, size(event_list)-2) AS i
            WITH a, event_list[i] AS e1, event_list[i+1] AS e2
            WHERE not (e1.relation = 'confounder' AND e2.relation = 'collider')
            MERGE (e1)-[df:DF {Type: a.Type, ID: a.Value, edge_weight: 1}]->(e2)
           """
    return Query(text, {"trigger": trigger})


def reveal_causal_relationships_queries(trigger: str, target: str) -> list[Query]:
    """The 6 queries Utils/causal_query_lib.py's reveal_causal_rels() runs, parameterized."""

    return [
        _find_causal_node_query(trigger, target, "confounder"),
        _set_causal_rels_query(trigger, target, "confounder"),
        _find_causal_node_query(trigger, target, "collider"),
        _set_causal_rels_query(trigger, target, "collider"),
        _set_target_df_query(trigger, target),
        _set_trigger_df_query(trigger),
    ]
