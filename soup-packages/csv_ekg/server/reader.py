"""
------------------------------------------------------------------------
File : reader.py
Description: read_csv() - reads a CSV into an EventLogData in the flat
             shape (moved here from the csv_reader package's
             CsvEventLogReader, removed in commit 8). Kept deliberately
             thin: pd.read_csv(dtype=str) so pandas never guesses types
             (the legacy bug this fixes: without dtype=str, pandas turned
             integer ids with empty cells into floats, "1" -> "1.0"),
             then from_dataframe() does the one pandas->Table
             conversion. All further normalization (spaces, millisecond
             comma, entity extraction, canonical CSV) is the ekg
             package's EventLog, not duplicated here.
Project : soup-packages/csv_ekg
------------------------------------------------------------------------
"""

from __future__ import annotations

from typing import BinaryIO

import pandas as pd
from soup_pkg_ekg.api import EventLogData, from_dataframe

from soup.core.contracts import ValidationError

FORMAT_ID = "csv"


def read_csv(stream: BinaryIO) -> EventLogData:
    """:raises ValidationError: not a readable CSV"""

    try:
        frame = pd.read_csv(stream, dtype=str)
    except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError) as exc:
        raise ValidationError(f"The file is not a readable CSV: {exc}") from exc
    return EventLogData(events=from_dataframe(frame))
