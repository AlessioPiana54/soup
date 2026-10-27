"""
------------------------------------------------------------------------
File : api.py
Description: Public API of the csv_table package. Other packages import
             it as soup_pkg_csv_table.api, and only if they list
             "csv_table" in their `requires`: the contributions (built on
             a ParsedCache of their own, or on the one given), the cache
             of the parsed tables and read_table(obj, tools), the columns
             and rows of a "table" object (the caller declares "storage").
Project : soup-packages/csv_table
------------------------------------------------------------------------
"""

from .cache import DEFAULT_MAX_BYTES, DEFAULT_MAX_OBJECTS, ParsedCache, limits_from_env
from .contributions import (
    KIND,
    ColumnDistribution,
    CsvExporter,
    CsvProfileVisualizer,
    CsvTableImporter,
    CsvTableVisualizer,
    new_cache,
    read_table,
)

__all__ = [
    "DEFAULT_MAX_BYTES",
    "DEFAULT_MAX_OBJECTS",
    "KIND",
    "ColumnDistribution",
    "CsvExporter",
    "CsvProfileVisualizer",
    "CsvTableImporter",
    "CsvTableVisualizer",
    "ParsedCache",
    "limits_from_env",
    "new_cache",
    "read_table",
]
