"""
------------------------------------------------------------------------
File : extension_points.py
Description: ExtensionPoints - named points a package opens
             (add_extension_point) so other packages can contribute
             items to it (contribute) without the core knowing what the
             items are. The owner reads them back with contributions(),
             ordered by `order` and then by registration. Copy-on-write,
             like Registry: changes replace the whole state with one
             assignment under a lock, reads use the current snapshot
             without locking.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import threading
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from soup.core.contracts import ExtensionPointError, PluginConflictError


@dataclass(frozen=True)
class _Contribution:
    key: str
    item: Any
    order: int
    owner: str
    sequence: int


@dataclass(frozen=True)
class _State:
    owners: Mapping[str, str] = field(default_factory=dict)
    contributions: Mapping[str, Mapping[str, _Contribution]] = field(default_factory=dict)
    sequence: int = 0


class ExtensionPoints:
    def __init__(self) -> None:
        self._state = _State()
        self._lock = threading.Lock()

    def add_point(self, name: str, owner: str) -> None:
        if not isinstance(name, str) or not name:
            raise ExtensionPointError("Extension point name must be a non-empty string")
        with self._lock:
            state = self._state
            if name in state.owners:
                raise PluginConflictError("extension_point", name, state.owners[name], owner)
            self._state = _State(
                {**state.owners, name: owner}, {**state.contributions, name: {}}, state.sequence
            )

    def contribute(self, point: str, item: Any, key: str, order: int, owner: str) -> None:
        if not isinstance(key, str) or not key:
            raise ExtensionPointError(f"Contribution key for '{point}' must be a non-empty string")
        with self._lock:
            state = self._state
            contributions = self._point(state, point)
            if key in contributions:
                raise PluginConflictError(f"contribution to '{point}'", key, contributions[key].owner, owner)
            sequence = state.sequence + 1
            added = {**contributions, key: _Contribution(key, item, int(order), owner, sequence)}
            self._state = _State(state.owners, {**state.contributions, point: added}, sequence)

    def contributions(self, point: str) -> list[Any]:
        ordered = sorted(self._point(self._state, point).values(), key=lambda c: (c.order, c.sequence))
        return [contribution.item for contribution in ordered]

    def owner_of(self, point: str) -> str:
        state = self._state
        self._point(state, point)
        return state.owners[point]

    def points(self) -> list[str]:
        return list(self._state.owners)

    def remove_owner(self, owner: str) -> None:
        """Drop the points `owner` opened and everything it contributed."""

        with self._lock:
            state = self._state
            owners = {name: point_owner for name, point_owner in state.owners.items() if point_owner != owner}
            contributions = {
                name: {key: c for key, c in items.items() if c.owner != owner}
                for name, items in state.contributions.items()
                if name in owners
            }
            self._state = _State(owners, contributions, state.sequence)

    @staticmethod
    def _point(state: _State, name: str) -> Mapping[str, _Contribution]:
        if name not in state.contributions:
            raise ExtensionPointError(f"Unknown extension point '{name}'")
        return state.contributions[name]
