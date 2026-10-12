"""
------------------------------------------------------------------------
File : tables.py
Description: to_dataframe()/from_dataframe() - the ONLY point of contact
             with pandas in soup/core. Plugins that are more convenient
             to write against a DataFrame (e.g. csv_reader, which reads
             via pd.read_csv) use this as a helper to convert back into
             the pandas-free Table contract; nothing in soup/core/
             contracts ever imports pandas.
Project : soup-server
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
