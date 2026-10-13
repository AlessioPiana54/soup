"""
------------------------------------------------------------------------
File : schema.py
Description: The core's EKG queries, rewritten as parameterized Query
             objects from Utils/graph_query_lib.py (not modified by this
             session - the legacy query functions stay in place and in
             use by the old, still-registered read/filter blueprints).

             Rule applied throughout: values that can be bound as Cypher
             parameters ($params) always are; values that cannot
             (labels, relationship types, property keys - a genuine
             Cypher limitation, not a parametrization we skipped) are
             validated and quoted with ident() before being spliced into
             the query text. Nothing here ever interpolates raw,
             unvalidated external input into query text.

             Column names (event id/timestamp/activity/extra property
             keys) come from ColumnMapping, itself built from the
             request's form fields - i.e. they originate from the HTTP
             request, which is exactly the case ident() exists for.

             The in-container CSV path (events_csv_path/entities_csv_path)
             is not raw user input either: it is built by
             DatasetRepository from a dataset name that repository has
             already validated (soup.core.dataset_repository._validate_name
             rejects empty/"."/".."/path separators). _quote_path() still
             escapes it defensively before splicing it into the LOAD CSV
             clause, whose target Memgraph does not accept as a $parameter.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from typing import Sequence

from soup.core.contracts import Query, ident

# Canonical column names written by EventLog.events_csv()/entities_csv()
# (soup/core/event_log.py) - fixed by the core's own schema, never user
# input, so they are safe to reference literally (no ident() needed).
EVENT_ID_FIELD = "event_id"
TIMESTAMP_FIELD = "timestamp"
ACTIVITY_FIELD = "activity_name"
ENTITY_VALUE_FIELD = "value"
ENTITY_TYPE_FIELD = "type"


def _quote_path(path: str) -> str:
    """Defensively escape a (repository-validated) path for a Cypher string literal."""

    escaped = path.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


def load_events_query(csv_path: str, extra_columns: Sequence[str] = ()) -> Query:
    """
    LOAD CSV -> CREATE (:Event {Event_Id, Timestamp, ActivityName, ...}).
    Mirrors Utils/graph_query_lib.py's load_event_node_query(), fixed to
    the canonical column names EventLog.events_csv() always writes
    (event_id/timestamp/activity_name), plus one property per extra
    column EventLog kept (entity and/or value columns).
    """

    event_id_prop = f"row.{ident(EVENT_ID_FIELD)}"
    timestamp_prop = f"row.{ident(TIMESTAMP_FIELD)}"
    activity_prop = f"row.{ident(ACTIVITY_FIELD)}"

    properties = [
        f"Event_Id: {event_id_prop}",
        f"Timestamp: localDateTime({timestamp_prop})",
        f"ActivityName: {activity_prop}",
    ]
    for column in extra_columns:
        column_ident = ident(column)
        properties.append(f"{column_ident}: row.{column_ident}")

    text = (
        f"LOAD CSV FROM {_quote_path(csv_path)} WITH HEADER AS row "
        f"CREATE (e:Event {{{', '.join(properties)}}})"
    )
    return Query(text)


def load_entities_query(csv_path: str) -> Query:
    """LOAD CSV -> MERGE (:Entity {Value, Type}). Mirrors load_entity_node_query()."""

    text = (
        f"LOAD CSV FROM {_quote_path(csv_path)} WITH HEADER AS row "
        f"MERGE (e:Entity {{Value: row.{ENTITY_VALUE_FIELD}, Type: row.{ENTITY_TYPE_FIELD}}})"
    )
    return Query(text)


# ---------------------------------------------------------------------- #
# Indexes - an explicit list, created and dropped together (correction of
# the legacy bug where drop_event_index() in Utils/general_query_lib.py
# tried to drop :Event(Event_Id), an index the build never actually
# creates - see Services/generic_graph_service.py's create_complete_graphs_s,
# which only ever calls create_entity_index() and create_event_index()).
# ---------------------------------------------------------------------- #

def create_entity_value_index() -> Query:
    return Query("CREATE INDEX ON :Entity(Value)")


def create_event_activity_index() -> Query:
    return Query("CREATE INDEX ON :Event(ActivityName)")


def drop_entity_value_index() -> Query:
    return Query("DROP INDEX ON :Entity(Value)")


def drop_event_activity_index() -> Query:
    return Query("DROP INDEX ON :Event(ActivityName)")


CREATED_INDEXES = (create_entity_value_index, create_event_activity_index)
DROPPED_INDEXES = (drop_entity_value_index, drop_event_activity_index)


def create_corr_relationships_query(entity_type: str) -> Query:
    """
    :CORR an Event to each Entity referenced by its (possibly
    comma-separated) `entity_type` property. Mirrors
    create_corr_relation_query(): `entity_type` is a column/property name
    and cannot be parametrized (quoted via ident()); the CORR
    relationship's own Type VALUE is the same string, passed as $entity_type.
    """

    property_ident = ident(entity_type)
    text = f"""
            MATCH (e:Event)
            WITH e,
                CASE WHEN toString(e.{property_ident}) <> "nan"
                    THEN split(e.{property_ident}, ',')
                    ELSE [e.{property_ident}]
                END AS entities
            UNWIND entities AS entity_id
            WITH DISTINCT entity_id, e
            MATCH (ent:Entity {{Value: entity_id}})
            MERGE (e)-[c:CORR {{Type: $entity_type}}]->(ent)
            """
    return Query(text, {"entity_type": entity_type})


def create_df_relationships_query(entity_type: str) -> Query:
    """
    :DF-chain the Events correlated to each Entity of `entity_type`, in
    Timestamp order. Mirrors create_df_relation_query(); nothing here
    needs ident() - every identifier is a fixed label/property of the
    core's own schema, and `entity_type` is only ever used as a $parameter.
    """

    text = """
            MATCH (e:Event)-[:CORR]->(n:Entity)
            WHERE n.Type = $entity_type
            WITH n, e AS nodes ORDER BY e.Timestamp, ID(e)
            WITH n, collect(nodes) AS event_node_list
            UNWIND range(0, size(event_node_list)-2) AS i
            WITH n, event_node_list[i] AS e1, event_node_list[i+1] AS e2
            MERGE (e1)-[df:DF {Type: n.Type, ID: n.Value, edge_weight: 1}]->(e2)
            """
    return Query(text, {"entity_type": entity_type})


def delete_events_query() -> Query:
    return Query("MATCH (e:Event) DETACH DELETE e")


def delete_entities_query() -> Query:
    return Query("MATCH (e:Entity) DETACH DELETE e")


def count_event_nodes_query() -> Query:
    return Query("MATCH (n:Event) RETURN COUNT(n) AS count")


def count_entity_nodes_query() -> Query:
    return Query("MATCH (n:Entity) RETURN COUNT(n) AS count")


def count_corr_relationships_query() -> Query:
    return Query("MATCH (:Event)-[corr:CORR]->(:Entity) RETURN COUNT(corr) AS count")


def count_df_relationships_query() -> Query:
    return Query("MATCH (:Event)-[df:DF]->(:Event) RETURN COUNT(df) AS count")
