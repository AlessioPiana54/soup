"""
------------------------------------------------------------------------
File : store.py
Description: What the contributions of ocel share:
             - the tables of an "ocel_tables" object in the package's
               storage space, one folder per object
               (storage.space("ocel").subspace(<object id>)): a JSON file
               per table of model.TABLES plus types.json (the declared
               event and object types); save, read, dispose;
             - OcelTables, all the tables of one object as read once, and
               CachedTables, the base of the contributions that read them
               through the plugin's ParsedCache (cache.py);
             - the meta of an import (file name and extension, counts,
               events and objects per type);
             - OcelImporterBase: the extensions (.json, .jsonocel) and
               the inspect() of both importers, a "keyvalue" summary and
               the first events as a "table".
             Standard library and the "storage" tool only.
Project : soup-packages/ocel
------------------------------------------------------------------------
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Optional

from soup.core.contracts import Importer, Inspection, NotFoundError, ObjectRef, Upload, report

from .cache import DEFAULT_MAX_BYTES, DEFAULT_MAX_OBJECTS, ParsedCache
from .model import TABLES, OcelLog, StoredTable, events_table, from_tables, parse, to_tables, types_document

TABLES_KIND = "ocel_tables"
NAMESPACE = "ocel"
STORAGE = "storage"
MEMGRAPH = "memgraph"
FORMAT_ID = "ocel2_json"

EXTENSIONS = (".json", ".jsonocel")
DEFAULT_EXTENSION = ".json"
TYPES_FILE = "types.json"
PREVIEW_EVENTS = 20


def extension_of(filename: str) -> str:
    lowered = filename.lower()
    return next((extension for extension in EXTENSIONS if lowered.endswith(extension)), DEFAULT_EXTENSION)


def import_meta(log: OcelLog, filename: str) -> dict[str, Any]:
    """What both importers keep in the meta about the file and its log."""

    return {
        "filename": filename,
        "extension": extension_of(filename),
        "counts": log.counts(),
        "events_per_type": log.events_per_type(),
        "objects_per_type": log.objects_per_type(),
    }


def summary_block(log: OcelLog) -> dict[str, Any]:
    counts = log.counts()
    return report.keyvalue({
        "eventi": counts["events"],
        "oggetti": counts["objects"],
        "tipi di evento": counts["event_types"],
        "tipi di oggetto": counts["object_types"],
    }, title="OCEL 2.0")


def first_events_block(log: OcelLog) -> dict[str, Any]:
    events = events_table(log, PREVIEW_EVENTS)
    return report.table(
        list(events.columns), [list(row) for row in events.rows], total=len(log.events),
        title=f"Primi {PREVIEW_EVENTS} eventi",
    )


class OcelImporterBase(Importer):
    """The format and the inspect() shared by the two importers of the package."""

    extensions = EXTENSIONS

    def inspect(self, upload: Upload, tools) -> Inspection:
        log = parse(upload.read())
        return Inspection(preview=(summary_block(log), first_events_block(log)))


# ---------------------------------------------------------------------- #
# The tables of an "ocel_tables" object
# ---------------------------------------------------------------------- #
def _space(tools):
    return tools.get(STORAGE).space(NAMESPACE)


def _folder(obj: ObjectRef, tools):
    return _space(tools).subspace(obj.id)


def save_tables(obj: ObjectRef, log: OcelLog, tools) -> None:
    folder = _folder(obj, tools)
    for name, table in to_tables(log).items():
        folder.write(f"{name}.json", table.to_json())
    folder.write(TYPES_FILE, json.dumps(types_document(log), ensure_ascii=False).encode("utf-8"))


def read_table(obj: ObjectRef, name: str, tools) -> StoredTable:
    if name not in TABLES:
        raise NotFoundError(f"An OCEL log has no table '{name}'")
    folder = _folder(obj, tools)
    if not folder.exists(f"{name}.json"):
        raise NotFoundError(f"Object '{obj.id}' has no stored table '{name}'")
    return StoredTable.from_json(folder.read(f"{name}.json"))


@dataclass(frozen=True)
class OcelTables:
    """
    Every table of an object and its types.json, as kept in the cache:
    shared by concurrent requests, so never modified (read-only mapping,
    StoredTable is frozen, the types stay JSON text).
    """

    tables: Mapping[str, StoredTable]
    types: str

    def table(self, name: str) -> StoredTable:
        if name not in self.tables:
            raise NotFoundError(f"An OCEL log has no table '{name}'")
        return self.tables[name]

    def log(self) -> OcelLog:
        return from_tables(self.tables, json.loads(self.types))


def load_tables(obj: ObjectRef, tools) -> OcelTables:
    """All the tables of `obj`, read from the storage (not from a cache)."""

    tables = {name: read_table(obj, name, tools) for name in TABLES}
    types = _folder(obj, tools).read(TYPES_FILE).decode("utf-8")
    return OcelTables(MappingProxyType(tables), types)


def read_log(obj: ObjectRef, tools) -> OcelLog:
    """The log kept by save_tables, rebuilt from its tables read from the storage."""

    return load_tables(obj, tools).log()


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

    def __init__(self, cache: Optional[ParsedCache[OcelTables]] = None):
        self.cache = cache if cache is not None else new_cache()

    def _tables(self, obj: ObjectRef, tools) -> OcelTables:
        return self.cache.get(obj.id, lambda: load_tables(obj, tools))


def dispose_tables(obj: ObjectRef, tools) -> None:
    # Also called after a failed import_(): the folder may not exist (a no-op then).
    _space(tools).delete(obj.id)
