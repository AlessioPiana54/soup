"""
------------------------------------------------------------------------
File : registry.py
Description: Generic, typed registry of plugin contributions. Every
             contribution is attributed to the plugin ("owner") that
             registered it, so a key conflict names both plugins involved.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from typing import Callable, Generic, Iterator, Optional, TypeVar

from soup.core.contracts import PluginConflictError

T = TypeVar("T")


class Registry(Generic[T]):
    """
    Keeps contributions of a single `kind` (e.g. "input_reader"),
    keyed by a unique string, each attributed to its owning plugin.
    Iterating the registry yields items ordered by their `order`
    attribute when present (default 0), falling back to insertion
    order for items with equal (or missing) `order`.
    """

    def __init__(self, kind: str):
        self.kind = kind
        self._items: dict[str, T] = {}
        self._owners: dict[str, str] = {}

    def register(self, item: T, owner: str, key: str) -> None:
        """
        Register `item` under `key`, attributed to `owner`.
        :raises PluginConflictError: if `key` is already registered by
            another owner, naming both the existing and the new owner.
        """

        if key in self._items:
            raise PluginConflictError(self.kind, key, self._owners[key], owner)
        self._items[key] = item
        self._owners[key] = owner

    def remove_owner(self, owner: str) -> list[str]:
        """
        Remove every item registered by `owner` (a package being rolled
        back or deactivated) and return their keys.
        """

        keys = [key for key, item_owner in self._owners.items() if item_owner == owner]
        for key in keys:
            del self._items[key]
            del self._owners[key]
        return keys

    def get(self, key: str) -> Optional[T]:
        return self._items.get(key)

    def owner_of(self, key: str) -> Optional[str]:
        return self._owners.get(key)

    def find(self, pred: Callable[[T], bool]) -> list[T]:
        return [item for item in self._ordered_items() if pred(item)]

    def keys(self) -> list[str]:
        return list(self._items.keys())

    def __iter__(self) -> Iterator[T]:
        return iter(self._ordered_items())

    def __len__(self) -> int:
        return len(self._items)

    def __contains__(self, key: object) -> bool:
        return key in self._items

    def _ordered_items(self) -> list[T]:
        # sorted() is stable: items sharing the same (or missing) `order`
        # keep their relative registration order.
        return sorted(self._items.values(), key=lambda item: getattr(item, "order", 0))
