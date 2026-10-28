"""
------------------------------------------------------------------------
File : catalog_ports.py
Description: The two halves of the Catalog contract, as the core's
             services use it (interface segregation): CatalogReader for
             who only looks objects up (resolving an id, listing the
             workspace, reading a thumbnail), CatalogWriter for who adds,
             changes or removes them. Any Catalog satisfies both (typing
             Protocols: structural, nothing to inherit); the contract in
             soup.core.contracts.tools is unchanged.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import builtins
from typing import Protocol

from soup.core.contracts import ObjectRef


class CatalogReader(Protocol):
    def get(self, object_id: str) -> ObjectRef | None: ...

    def list(self) -> list[ObjectRef]: ...

    def children(self, object_id: str) -> builtins.list[ObjectRef]: ...

    def get_thumbnail(self, object_id: str) -> str | None: ...


class CatalogWriter(Protocol):
    def add(self, obj: ObjectRef) -> None: ...

    def update(self, obj: ObjectRef) -> None: ...

    def remove(self, object_id: str) -> None: ...

    def set_thumbnail(self, object_id: str, svg: str | None) -> None: ...
