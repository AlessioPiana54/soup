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
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from typing import Any, Mapping

from soup.core.contracts import EVENT_LOG, BuildContext, EventLogData, InputHandler
from soup.core.dataset_repository import DatasetRepository
from soup.core.event_log import ColumnMapping, EventLog
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

        config = {
            "dataset_name": dataset_name,
            "dataset_description": options.get("dataset_description"),
            "all_columns": options.get("all_columns", []),
            "standard_columns": options.get("standard_columns", []),
            "filtered_columns": options.get("filtered_columns", []),
            "values_columns": options.get("values_columns", []),
            "trigger_target_rows": options.get("trigger_target_rows", []),
            "source_format": options.get("source_format"),
            "event_nodes": 0,
            "entity_nodes": 0,
            "corr_rel": 0,
            "df_rel": 0,
            "date_created": None,
            "date_modified": None,
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

        config.update(self._ekg_service.counts())
        config["date_created"] = timer.started_at
        config["date_modified"] = timer.finished_at
        self._repository.save_config(dataset_name, config)

        return Result(http_status_code=201, message="Create graph successfully", response_data="success")
