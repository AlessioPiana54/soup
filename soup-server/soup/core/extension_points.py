"""
------------------------------------------------------------------------
File : extension_points.py
Description: ExtensionPoints - named points a package opens
             (add_extension_point) so other packages can contribute
             items to it (contribute) without the core knowing what the
             items are. The owner reads them back with contributions(),
             ordered by `order` and then by registration.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from soup.core.contracts import ExtensionPointError, PluginConflictError


@dataclass(frozen=True)
class _Contribution:
    key: str
    item: Any
    order: int
    owner: str
    sequence: int


class ExtensionPoints:
    def __init__(self) -> None:
        self._owners: dict[str, str] = {}
        self._contributions: dict[str, dict[str, _Contribution]] = {}
        self._sequence = 0

    def add_point(self, name: str, owner: str) -> None:
        if not isinstance(name, str) or not name:
            raise ExtensionPointError("Extension point name must be a non-empty string")
        if name in self._owners:
            raise PluginConflictError("extension_point", name, self._owners[name], owner)
        self._owners[name] = owner
        self._contributions[name] = {}

    def contribute(self, point: str, item: Any, key: str, order: int, owner: str) -> None:
        contributions = self._point(point)
        if not isinstance(key, str) or not key:
            raise ExtensionPointError(f"Contribution key for '{point}' must be a non-empty string")
        if key in contributions:
            raise PluginConflictError(f"contribution to '{point}'", key, contributions[key].owner, owner)
        self._sequence += 1
        contributions[key] = _Contribution(key, item, int(order), owner, self._sequence)

    def contributions(self, point: str) -> list[Any]:
        ordered = sorted(self._point(point).values(), key=lambda c: (c.order, c.sequence))
        return [contribution.item for contribution in ordered]

    def owner_of(self, point: str) -> str:
        self._point(point)
        return self._owners[point]

    def points(self) -> list[str]:
        return list(self._owners)

    def remove_owner(self, owner: str) -> None:
        """Drop the points `owner` opened and everything it contributed."""

        for name in [name for name, point_owner in self._owners.items() if point_owner == owner]:
            del self._owners[name]
            del self._contributions[name]
        for contributions in self._contributions.values():
            for key in [key for key, c in contributions.items() if c.owner == owner]:
                del contributions[key]

    def _point(self, name: str) -> dict[str, _Contribution]:
        if name not in self._contributions:
            raise ExtensionPointError(f"Unknown extension point '{name}'")
        return self._contributions[name]
