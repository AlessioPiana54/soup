"""
------------------------------------------------------------------------
File : registry.py
Description: Generic, typed registry of plugin contributions. Every
             contribution is attributed to the plugin ("owner") that
             registered it, so a key conflict names both plugins involved.
             Copy-on-write: packages are installed, enabled, disabled and
             uninstalled while requests read the registries, so every
             change builds a new snapshot and publishes it with a single
             assignment under a lock; readers take the current snapshot
             once and never lock. entries() lists (key, package, item)
             from one snapshot, so a router never pairs an item with a
             key read from a later state.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Callable, Generic, Iterator, Mapping, Optional, TypeVar

from soup.core.contracts import PluginConflictError

T = TypeVar("T")


@dataclass(frozen=True)
class Registered(Generic[T]):
    """A contribution as listed from one snapshot: its key, its package (owner) and the item."""

    key: str
    package: str
    item: T


@dataclass(frozen=True)
class _Snapshot(Generic[T]):
    """One immutable state of a Registry. Never modified after creation."""

    items: Mapping[str, T] = field(default_factory=dict)
    owners: Mapping[str, str] = field(default_factory=dict)
    # Sorted by the item's `order` (then registration), computed once per change.
    entries: tuple[Registered[T], ...] = ()
    ordered: tuple[T, ...] = ()


def _snapshot(items: dict[str, T], owners: dict[str, str]) -> _Snapshot[T]:
    # sorted() is stable: items sharing the same (or missing) `order`
    # keep their relative registration order.
    entries = tuple(sorted(
        (Registered(key, owners[key], item) for key, item in items.items()),
        key=lambda entry: getattr(entry.item, "order", 0),
    ))
    return _Snapshot(items, owners, entries, tuple(entry.item for entry in entries))


class Registry(Generic[T]):
    """
    Keeps contributions of a single `kind` (e.g. "importer"), keyed by a
    unique string, each attributed to its owning plugin. Iterating the
    registry yields items ordered by their `order` attribute when present
    (default 0), falling back to insertion order for items with equal (or
    missing) `order`.
    """

    def __init__(self, kind: str):
        self.kind = kind
        self._state: _Snapshot[T] = _Snapshot()
        self._lock = threading.Lock()

    def register(self, item: T, owner: str, key: str) -> None:
        """
        Register `item` under `key`, attributed to `owner`.
        :raises PluginConflictError: if `key` is already registered by
            another owner, naming both the existing and the new owner.
        """

        with self._lock:
            state = self._state
            if key in state.items:
                raise PluginConflictError(self.kind, key, state.owners[key], owner)
            self._state = _snapshot({**state.items, key: item}, {**state.owners, key: owner})

    def remove_owner(self, owner: str) -> list[str]:
        """
        Remove every item registered by `owner` (a package being rolled
        back or deactivated) and return their keys.
        """

        with self._lock:
            state = self._state
            keys = [key for key, item_owner in state.owners.items() if item_owner == owner]
            if keys:
                self._state = _snapshot(
                    {key: item for key, item in state.items.items() if key not in keys},
                    {key: item_owner for key, item_owner in state.owners.items() if key not in keys},
                )
            return keys

    def get(self, key: str) -> Optional[T]:
        return self._state.items.get(key)

    def owner_of(self, key: str) -> Optional[str]:
        return self._state.owners.get(key)

    def keys_of(self, owner: str) -> list[str]:
        """The keys registered by `owner`, in registration order."""

        return [key for key, item_owner in self._state.owners.items() if item_owner == owner]

    def entries(self) -> list[Registered[T]]:
        """Every contribution with its key and package, ordered like iteration."""

        return list(self._state.entries)

    def find(self, pred: Callable[[T], bool]) -> list[T]:
        return [item for item in self._state.ordered if pred(item)]

    def keys(self) -> list[str]:
        return list(self._state.items.keys())

    def __iter__(self) -> Iterator[T]:
        return iter(self._state.ordered)

    def __len__(self) -> int:
        return len(self._state.items)

    def __contains__(self, key: object) -> bool:
        return key in self._state.items
