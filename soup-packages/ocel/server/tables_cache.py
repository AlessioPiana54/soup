"""
------------------------------------------------------------------------
File : tables_cache.py
Description: The cache of the tables of the "ocel_tables" objects: the
             ParsedCache of soup_base (soup_pkg_soup_base.api) keyed by
             object id, with the estimated size of an OcelTables, and
             CachedTables, the base of the contributions that read the
             tables through the plugin's cache (one read per object;
             import_() and dispose() invalidate the entry).
Project : soup-packages/ocel
------------------------------------------------------------------------
"""

from __future__ import annotations

from typing import Any

from soup_pkg_soup_base.api import DEFAULT_MAX_BYTES, DEFAULT_MAX_OBJECTS, ParsedCache

from soup.core.contracts import ObjectRef, ToolAccess

from .store import OcelTables, load_tables

# Rough CPython sizes: a str object without its characters, any other
# scalar, one item reference, the containers of a table.
_STR_OVERHEAD = 49
_SCALAR = 32
_POINTER = 8
_CONTAINERS = 200


def _cell_size(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, str):
        return _STR_OVERHEAD + len(value)
    return _SCALAR


def estimated_size(value: OcelTables) -> int:
    """Estimated memory, in bytes, of the tables of an object."""

    size = _STR_OVERHEAD + len(value.types)
    for table in value.tables.values():
        size += _CONTAINERS + _POINTER * len(table.rows)
        size += sum(_POINTER * len(row) + sum(_cell_size(cell) for cell in row) for row in table.rows)
    return size


def new_cache(max_objects: int = DEFAULT_MAX_OBJECTS, max_bytes: int = DEFAULT_MAX_BYTES) -> ParsedCache[OcelTables]:
    return ParsedCache(estimated_size, max_objects=max_objects, max_bytes=max_bytes)


class CachedTables:
    """Base of the contributions that read the stored tables through a ParsedCache (one read per object)."""

    def __init__(self, cache: ParsedCache[OcelTables] | None = None):
        self.cache = cache if cache is not None else new_cache()

    def _tables(self, obj: ObjectRef, tools: ToolAccess) -> OcelTables:
        return self.cache.get(obj.id, lambda: load_tables(obj, tools))
