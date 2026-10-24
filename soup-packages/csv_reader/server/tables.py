"""
------------------------------------------------------------------------
File : tables.py
Description: to_dataframe()/from_dataframe() - conversion between a pandas
             DataFrame and the pandas-free Table contract. Moved here
             from soup/core/tables.py: csv_reader was its only user, and
             the core no longer imports pandas.
Project : soup-packages/csv_reader
------------------------------------------------------------------------
"""

from __future__ import annotations

import pandas as pd

from soup.core.contracts import Table


def to_dataframe(table: Table) -> pd.DataFrame:
    """Convert a Table into a pandas DataFrame of strings/NaN."""

    return pd.DataFrame(list(table.rows), columns=list(table.columns))


def from_dataframe(frame: pd.DataFrame) -> Table:
    """
    Convert a pandas DataFrame into a Table: every cell becomes a string
    or None (NaN/NA -> None). Column names are coerced to str.
    """

    columns = tuple(str(column) for column in frame.columns)
    rows = tuple(
        tuple(None if pd.isna(value) else str(value) for value in record)
        for record in frame.itertuples(index=False, name=None)
    )
    return Table(columns, rows)
