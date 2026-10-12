"""
------------------------------------------------------------------------
File : event_log.py
Description: EventLogData and EventLogReader - the event-log
             specialization of the generic input contracts (input.py).
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from soup.core.contracts.input import EVENT_LOG, InputReader
from soup.core.contracts.tables import Table


@dataclass(frozen=True)
class EventLogData:
    """
    What an EventLogReader hands to the core, before any normalization,
    millisecond fix-up or mapping validation (all of that is
    EventLog.from_data's job, in soup/core). All values are text or None.

    Two shapes are accepted:

    - Flat: only `events` is set. Each row is one event; object
      references live in the events table's own columns, with several
      objects in one cell separated by a comma (e.g. "i1,i2") - this is
      what today's CSV import produces.

    - Separated (OCEL 2.0-style): `events` holds only event attributes;
      `objects` holds one row per object (object_id, object_type, plus
      any attribute columns); `event_objects` links event_id to
      object_id (with an optional, currently-unused `qualifier` column).
      A reader for a format that already separates events from objects
      (e.g. a future OCEL reader) returns this shape instead of flattening
      it itself - EventLog.from_data does the flattening once, in the
      core, so every such format gets the exact same behaviour.
    """

    events: Table
    objects: Optional[Table] = None
    event_objects: Optional[Table] = None

    def __post_init__(self) -> None:
        if self.objects is not None:
            if "object_id" not in self.objects.columns or "object_type" not in self.objects.columns:
                raise ValueError(
                    "EventLogData.objects must have an 'object_id' and an 'object_type' column"
                )
        if self.event_objects is not None:
            if "event_id" not in self.event_objects.columns or "object_id" not in self.event_objects.columns:
                raise ValueError(
                    "EventLogData.event_objects must have an 'event_id' and an 'object_id' column "
                    "('qualifier' is optional)"
                )


class EventLogReader(InputReader[EventLogData]):
    """InputReader specialized for event logs."""

    kind = EVENT_LOG
