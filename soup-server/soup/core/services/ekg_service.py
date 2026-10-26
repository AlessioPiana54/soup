"""
------------------------------------------------------------------------
File : ekg_service.py
Description: EkgService - build/reset/rebuild the EKG for one dataset,
             merging the core's build steps (soup/core/ekg/steps.py) with
             whatever steps plugins contributed (PluginContext.add_build_step,
             e.g. soup-packages/causal_df), ordered by `.order`. The
             database is normally the "memgraph" tool, reached through
             soup/core/services/legacy_tools.ToolGraph.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from soup.core.contracts import BuildContext, EkgBuildStep, GraphDatabase
from soup.core.ekg import schema
from soup.core.ekg.steps import core_steps
from soup.core.registry import Registry


class EkgService:
    def __init__(self, db: GraphDatabase, plugin_build_steps: Registry[EkgBuildStep] | None = None):
        self._db = db
        self._plugin_build_steps = plugin_build_steps

    def build_pipeline(self) -> list[EkgBuildStep]:
        """
        The full, ordered list of build steps (core + plugin-contributed),
        independent of any particular BuildContext - useful to inspect/test
        the pipeline's composition without running it against a database.
        """

        plugin_steps = list(self._plugin_build_steps) if self._plugin_build_steps is not None else []
        return sorted((*core_steps(), *plugin_steps), key=lambda step: step.order)

    def build(self, ctx: BuildContext) -> None:
        for step in self.build_pipeline():
            if step.applies(ctx):
                step.execute(ctx, self._db)

    def reset(self) -> None:
        """
        Delete every Event/Entity node and drop exactly the indexes the
        build actually creates (schema.DROPPED_INDEXES) - unlike the
        legacy Services/Graph/op_graph_service.py's delete_graph_s(),
        which also tries to drop :Event(Event_Id), an index the build
        never creates, and which Memgraph then errors on.
        """

        self._db.run(schema.delete_events_query())
        self._db.run(schema.delete_entities_query())
        for factory in schema.DROPPED_INDEXES:
            self._db.run(factory())

    def invalidate(self) -> None:
        """
        This service writes outside the memgraph tool's ensure_loaded:
        tell the tool its active state is no longer what it loaded (a
        no-op for databases that do not track one).
        """

        invalidate = getattr(self._db, "invalidate", None)
        if callable(invalidate):
            invalidate()

    def rebuild(self, ctx: BuildContext) -> None:
        self.reset()
        self.build(ctx)

    def counts(self) -> dict[str, int]:
        """event_nodes/entity_nodes/corr_rel/df_rel - the counters the legacy
        config JSON stores (Services/generic_graph_service.py)."""

        return {
            "event_nodes": self._scalar_count(schema.count_event_nodes_query()),
            "entity_nodes": self._scalar_count(schema.count_entity_nodes_query()),
            "corr_rel": self._scalar_count(schema.count_corr_relationships_query()),
            "df_rel": self._scalar_count(schema.count_df_relationships_query()),
        }

    def _scalar_count(self, query) -> int:
        rows = self._db.run(query)
        if not rows:
            return 0
        return next(iter(rows[0].values()))
