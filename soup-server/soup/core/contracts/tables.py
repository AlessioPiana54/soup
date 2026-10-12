"""
------------------------------------------------------------------------
File : tables.py
Description: Table - the plain, textual, pandas-free data structure that
             flows between InputReader plugins and the core. Every cell
             is a string or None: type coercion/parsing is the core's job
             (EventLog.from_data), not the reader's. Zero dependencies.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Iterator, Mapping, Optional, Sequence


@dataclass(frozen=True)
class Table:
    """
    Immutable, rectangular table of text (or None) cells.

    :raises ValueError: if `columns` is empty, contains duplicates, or any
        row's length does not match the number of columns.
    """

    columns: tuple[str, ...]
    rows: tuple[tuple[Optional[str], ...], ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.columns, tuple):
            object.__setattr__(self, "columns", tuple(self.columns))
        if not isinstance(self.rows, tuple):
            object.__setattr__(self, "rows", tuple(tuple(row) for row in self.rows))

        if len(self.columns) == 0:
            raise ValueError("Table must have at least one column")
        if len(set(self.columns)) != len(self.columns):
            raise ValueError(f"Table columns must be unique, got {self.columns!r}")

        expected_length = len(self.columns)
        for index, row in enumerate(self.rows):
            if len(row) != expected_length:
                raise ValueError(
                    f"Row {index} has {len(row)} cells, expected {expected_length} "
                    f"(one per column {self.columns!r})"
                )

    # ------------------------------------------------------------------ #
    # Constructors
    # ------------------------------------------------------------------ #
    @classmethod
    def from_records(
        cls, records: Iterable[Mapping[str, Optional[str]]], columns: Optional[Sequence[str]] = None
    ) -> "Table":
        """Build a Table from an iterable of {column: value} dicts."""

        records = list(records)
        if columns is None:
            if not records:
                raise ValueError("Cannot infer columns from an empty list of records; pass `columns` explicitly")
            columns = list(records[0].keys())

        rows = tuple(tuple(record.get(column) for column in columns) for record in records)
        return cls(tuple(columns), rows)

    @classmethod
    def from_rows(cls, columns: Sequence[str], rows: Iterable[Sequence[Optional[str]]]) -> "Table":
        """Build a Table from an explicit column list and row-tuples/lists."""

        return cls(tuple(columns), tuple(tuple(row) for row in rows))

    # ------------------------------------------------------------------ #
    # Access helpers
    # ------------------------------------------------------------------ #
    def column_index(self, name: str) -> int:
        return self.columns.index(name)

    def iter_records(self) -> Iterator[dict]:
        for row in self.rows:
            yield dict(zip(self.columns, row))

    def __len__(self) -> int:
        return len(self.rows)

    def __iter__(self) -> Iterator[tuple[Optional[str], ...]]:
        return iter(self.rows)

    def __contains__(self, column: object) -> bool:
        return column in self.columns
