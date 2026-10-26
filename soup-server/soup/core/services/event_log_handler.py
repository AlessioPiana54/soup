"""
------------------------------------------------------------------------
File : event_log_handler.py
Description: EventLogHandler - the InputHandler the core registers for
             kind=EVENT_LOG: EventLog.from_data -> DatasetRepository.save
             (source_format = the reader's format_id) -> EkgService.build.
             If the build fails, the dataset just staged is removed and
             the error re-raised (compensating action, same intent as the
             legacy code's cleanup-on-failure in
             Services/Graph/graph_service.py's create_new_dataset_s).
             Either way the memgraph tool's active state is invalidated:
             the graph now holds this dataset (or a half-built one), not
             whatever ensure_loaded loaded last.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from typing import Any, Mapping

from soup.core.contracts import EVENT_LOG, BuildContext, EventLogData, InputHandler
from soup.core.dataset_repository import DatasetRepository
from soup.core.event_log import (
    ACTIVITY_COLUMN,
    EVENT_ID_COLUMN,
    TIMESTAMP_COLUMN,
    ColumnMapping,
    EventLog,
    _normalize_text,
)
from soup.core.process_timer import ProcessTimer
from soup.core.results import Result
from soup.core.services.ekg_service import EkgService


class EventLogHandler(InputHandler[EventLogData]):
    kind = EVENT_LOG

    def __init__(self, repository: DatasetRepository, ekg_service: EkgService):
        self._repository = repository
        self._ekg_service = ekg_service

    def handle(self, data: EventLogData, options: Mapping[str, Any]) -> Result:
        dataset_name = options.get("dataset_name")

        mapping = ColumnMapping.from_payload(
            options.get("standard_columns", []),
            filtered_columns=options.get("filtered_columns", []),
            values_columns=options.get("values_columns", []),
        )
        log = EventLog.from_data(data, mapping)

        self._repository.save_event_log(dataset_name, log.events_csv(), log.entities_csv())

        # filtered_columns/values_columns must match what the graph was
        # actually built with (log.mapping, already normalized by
        # EventLog.from_data), not the raw names the request came in with -
        # the legacy code that still reads this config (filters) looks these
        # columns up by their normalized form.
        #
        # standard_columns is different: GenericGraphService.create_complete_graphs_s
        # (legacy /complete-graph/build) uses these three values as literal
        # Cypher property names against the canonical events CSV - and that
        # CSV always writes the fixed "event_id"/"timestamp"/"activity_name"
        # headers for the standard roles (EventLog.events_csv), never the
        # original mapping names. So standard_columns must store those fixed
        # names, not log.mapping.event_id/timestamp/activity.
        config = {
            "dataset_name": dataset_name,
            "dataset_description": options.get("dataset_description"),
            "all_columns": [_normalize_text(column) for column in options.get("all_columns", [])],
            "standard_columns": [EVENT_ID_COLUMN, TIMESTAMP_COLUMN, ACTIVITY_COLUMN],
            "filtered_columns": list(log.mapping.entity_columns),
            "values_columns": list(log.mapping.value_columns),
            "trigger_target_rows": options.get("trigger_target_rows", []),
            "source_format": options.get("source_format"),
            "event_nodes": 0,
            "entity_nodes": 0,
            "corr_rel": 0,
            "df_rel": 0,
            "date_created": None,
            "date_modified": None,
            # Same shape as the legacy Models/dataset_process_info_model.py's
            # DatasetProcessInformation.to_dict() - the frontend
            # (support.service.ts's parseItemToDataset) reads this key
            # unconditionally for every dataset in the list, with no null
            # check, so it must always be present even though this pipeline
            # only ever fills in init_time/finish_time (the class/obs/dfc
            # phases belong to the separate aggregate-graph build, not import).
            "process_info": {
                "init_time": None,
                "finish_time": None,
                "init_class_time": None,
                "finish_class_time": None,
                "init_event_time": None,
                "finish_event_time": None,
                "init_entity_time": None,
                "finish_entity_time": None,
                "init_corr_time": None,
                "finish_corr_time": None,
                "init_df_time": None,
                "finish_df_time": None,
                "init_class_node_time": None,
                "finish_class_node_time": None,
                "init_obs_time": None,
                "finish_obs_time": None,
                "init_dfc_time": None,
                "finish_dfc_time": None,
            },
        }
        self._repository.save_config(dataset_name, config)

        ctx = BuildContext(
            dataset_name=dataset_name,
            mapping=log.mapping,
            events_csv_path=self._repository.events_csv_load_path(dataset_name),
            entities_csv_path=self._repository.entities_csv_load_path(dataset_name),
            trigger_target_rows=tuple(options.get("trigger_target_rows", [])),
        )

        try:
            with ProcessTimer() as timer:
                self._ekg_service.build(ctx)
        except Exception:
            # Compensating action: a dataset is never left half-built -
            # either both the staged files AND the graph exist, or neither.
            self._repository.delete(dataset_name)
            raise
        finally:
            self._ekg_service.invalidate()

        config.update(self._ekg_service.counts())
        config["date_created"] = timer.started_at
        config["date_modified"] = timer.finished_at
        config["process_info"]["init_time"] = timer.started_at
        config["process_info"]["finish_time"] = timer.finished_at
        self._repository.save_config(dataset_name, config)

        return Result(http_status_code=201, message="Create graph successfully", response_data="success")
