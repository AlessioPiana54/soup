"""
------------------------------------------------------------------------
File : step.py
Description: OcelRelationshipsStep - the build step ocel contributes to
             "ekg.build_steps". An EKG made from an OCEL 2.0 log (graph.py)
             stages two files with its dataset (build_ekg's extra_files);
             at the first build and at every rebuild the step reads them
             with LOAD CSV and adds to the graph:
             - ocel_qualifiers.csv (event_id, object_id, object_type,
               qualifier): the qualifier of an event-object relationship
               as the `qualifier` property of its :CORR;
             - ocel_o2o.csv (source_id, source_type, target_id,
               target_type, qualifier): the object-object relationships
               as (:Entity)-[:REL {qualifier}]->(:Entity) between the
               entities of the two objects (an object no event refers to
               has no :Entity, and its relationships are left out).
             One relationship type, REL: a qualifier is free text, so it
             is always a value (a property read from the row), never a
             type or a name in the text of the query.
             Order 420: after LoadEntitiesStep (200) and CorrelationStep
             (400), whose :Entity and :CORR it needs, and before
             causal_df (450) and DirectlyFollowsStep (500), which do not
             read what it adds; no other step has 420
             (tests/test_build_step_orders.py). Without the files (an EKG
             from a CSV, or from an OCEL log imported before) it does not
             apply.
Project : soup-packages/ocel
------------------------------------------------------------------------
"""

from __future__ import annotations

from soup_pkg_ekg.api import BuildContext, EkgBuildStep, GraphDatabase, Query, load_csv_clause

QUALIFIERS_FILE = "ocel_qualifiers.csv"
OBJECT_OBJECTS_FILE = "ocel_o2o.csv"
FILES = (QUALIFIERS_FILE, OBJECT_OBJECTS_FILE)
QUALIFIERS_COLUMNS = ("event_id", "object_id", "object_type", "qualifier")
OBJECT_OBJECTS_COLUMNS = ("source_id", "source_type", "target_id", "target_type", "qualifier")

# The same queries on rows passed as the parameter $rows instead of a file
# (memgraph_smoke.py of ekg_views).
ROWS = "UNWIND $rows AS row"


def qualifiers_query(source: str) -> Query:
    """`source` (LOAD CSV ... AS row, or ROWS): the qualifier of each :CORR of a row."""

    return Query(f"""
        {source}
        WITH row WHERE row.qualifier IS NOT NULL AND row.qualifier <> ''
        MATCH (n:Entity {{Value: row.object_id}})
        MATCH (n)<-[c:CORR {{Type: row.object_type}}]-(e:Event {{Event_Id: row.event_id}})
        SET c.qualifier = row.qualifier""")


def object_relationships_query(source: str) -> Query:
    """`source` (LOAD CSV ... AS row, or ROWS): a :REL for each row, with its qualifier if it has one."""

    return Query(f"""
        {source}
        MATCH (a:Entity {{Value: row.source_id, Type: row.source_type}})
        MATCH (b:Entity {{Value: row.target_id, Type: row.target_type}})
        CREATE (a)-[r:REL]->(b)
        SET r.qualifier = CASE WHEN row.qualifier = '' THEN null ELSE row.qualifier END""")


class OcelRelationshipsStep(EkgBuildStep):
    key = "ocel_relationships"
    order = 420

    def applies(self, ctx: BuildContext) -> bool:
        return any(file in ctx.extra_files for file in FILES)

    def execute(self, ctx: BuildContext, db: GraphDatabase) -> None:
        if QUALIFIERS_FILE in ctx.extra_files:
            db.run(qualifiers_query(load_csv_clause(ctx.extra_files[QUALIFIERS_FILE])))
        if OBJECT_OBJECTS_FILE in ctx.extra_files:
            db.run(object_relationships_query(load_csv_clause(ctx.extra_files[OBJECT_OBJECTS_FILE])))
