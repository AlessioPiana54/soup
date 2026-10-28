"""
------------------------------------------------------------------------
File : cache.py
Description: ParsedCache - a small in-memory LRU cache of the tables of
             an "ocel_tables" object already read from the storage and
             parsed, keyed by object id, so the visualizer actions (every
             page, filter or sort), the export and "Scomponi in EKG" do
             not read the files again: with DockerVolumeStorage each read
             copies the file out of the container. Bounded by number of
             objects and by estimated size; an entry larger than the size
             limit is never kept (it is read every time, as without a
             cache). Thread-safe. The Plugin creates one per instance in
             register(): there is no module-level cache shared between
             plugin instances.
             A copy of csv_table/server/cache.py (a package imports only
             the api.py of the packages it requires): the duplication goes
             away in commit 13.
Project : soup-packages/ocel
------------------------------------------------------------------------
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Callable, Generic, Mapping, TypeVar

V = TypeVar("V")

DEFAULT_MAX_OBJECTS = 8
DEFAULT_MAX_BYTES = 200 * 1024 * 1024


class ParsedCache(Generic[V]):
    """
    `size_of(value)` estimates the memory of a value in bytes. get() loads
    a missing value outside the lock; an invalidate() that happens while
    a value is being loaded wins: the stale value is returned to its
    caller but not kept.
    """

    def __init__(
        self,
        size_of: Callable[[V], int],
        max_objects: int = DEFAULT_MAX_OBJECTS,
        max_bytes: int = DEFAULT_MAX_BYTES,
    ):
        if max_objects < 1 or max_bytes < 1:
            raise ValueError("ParsedCache limits must be positive")
        self.max_objects = max_objects
        self.max_bytes = max_bytes
        self._size_of = size_of
        self._entries: OrderedDict[str, tuple[V, int]] = OrderedDict()
        self._bytes = 0
        # Bumped by every invalidate()/clear(): a load started before is not stored.
        self._version = 0
        self._lock = threading.Lock()

    def get(self, key: str, load: Callable[[], V]) -> V:
        with self._lock:
            entry = self._entries.get(key)
            if entry is not None:
                self._entries.move_to_end(key)
                return entry[0]
            version = self._version
        value = load()
        size = self._size_of(value)
        if size > self.max_bytes:
            return value
        with self._lock:
            if version != self._version:
                return value
            entry = self._entries.get(key)
            if entry is not None:
                # Loaded meanwhile by another request: keep the first one.
                self._entries.move_to_end(key)
                return entry[0]
            self._entries[key] = (value, size)
            self._bytes += size
            while len(self._entries) > self.max_objects or self._bytes > self.max_bytes:
                _, (_, evicted) = self._entries.popitem(last=False)
                self._bytes -= evicted
        return value

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._version += 1
            entry = self._entries.pop(key, None)
            if entry is not None:
                self._bytes -= entry[1]

    def clear(self) -> None:
        with self._lock:
            self._version += 1
            self._entries.clear()
            self._bytes = 0

    def keys(self) -> list[str]:
        """The cached keys, least recently used first."""

        with self._lock:
            return list(self._entries)

    @property
    def total_bytes(self) -> int:
        with self._lock:
            return self._bytes

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    def __contains__(self, key: object) -> bool:
        with self._lock:
            return key in self._entries


def _positive(env: Mapping[str, str], name: str, default: int) -> int:
    raw = env.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw.strip())
    except ValueError:
        raise ValueError(f"{name} must be a positive integer, got {raw!r}") from None
    if value < 1:
        raise ValueError(f"{name} must be a positive integer, got {raw!r}")
    return value


def limits_from_env(env: Mapping[str, str], prefix: str) -> tuple[int, int]:
    """
    (max objects, max bytes) from <prefix>_CACHE_OBJECTS and
    <prefix>_CACHE_MB, with the defaults (8 objects, 200 MB).
    :raises ValueError: a value that is not a positive integer
    """

    objects = _positive(env, f"{prefix}_CACHE_OBJECTS", DEFAULT_MAX_OBJECTS)
    megabytes = _positive(env, f"{prefix}_CACHE_MB", DEFAULT_MAX_BYTES // (1024 * 1024))
    return objects, megabytes * 1024 * 1024
