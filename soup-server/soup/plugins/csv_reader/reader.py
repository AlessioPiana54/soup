"""
------------------------------------------------------------------------
File : reader.py
Description: CsvEventLogReader - reads a CSV into an EventLogData in the
             flat shape. Kept deliberately thin: pd.read_csv(dtype=str)
             so pandas never guesses types (the legacy bug this fixes:
             without dtype=str, pandas turned integer ids with empty
             cells into floats, "1" -> "1.0"), then from_dataframe() does
             the one pandas->Table conversion. All further normalization
             (spaces, millisecond comma, entity extraction, canonical
             CSV) is common core logic in soup/core/event_log.py, not
             duplicated here.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from typing import BinaryIO

import pandas as pd

from soup.core.contracts import EventLogData, EventLogReader
from soup.core.tables import from_dataframe


class CsvEventLogReader(EventLogReader):
    format_id = "csv"
    label = "CSV"
    extensions = (".csv",)

    def read(self, stream: BinaryIO) -> EventLogData:
        frame = pd.read_csv(stream, dtype=str)
        return EventLogData(events=from_dataframe(frame))
