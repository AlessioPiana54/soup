"""
------------------------------------------------------------------------
File : tools.py
Description: Tool - a shared resource contributed by a package (graph
             database, file storage, object catalog, preferences, ...)
             and used by other packages that declare it in
             requires_tools. ToolAccess is what an importer/operation/
             visualizer/exporter receives to reach the tools it declared.
             Catalog and Preferences are the two tool ports the core
             itself depends on: packages provide them under the names
             CATALOG_TOOL and PREFERENCES_TOOL.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import builtins
from abc import ABC, abstractmethod
from typing import Any, Protocol, TypeVar

from soup.core.contracts.objects import ObjectRef

CATALOG_TOOL = "catalog"
PREFERENCES_TOOL = "preferences"

T = TypeVar("T", bound="Tool")


class Tool(ABC):
    """A named shared resource. `name` is unique among loaded tools."""

    name: str = ""

    @abstractmethod
    def health(self) -> dict[str, Any]:
        """
        Cheap status check, e.g. {"ok": True} or {"ok": False, "error":
        "..."}; must not raise.
        """
        raise NotImplementedError


class ToolAccess(Protocol):
    """
    Access to the tools a contribution declared in requires_tools.
    Asking for an undeclared tool raises ToolNotDeclaredError, even if
    the tool is loaded.
    """

    def get(self, name: str) -> Tool:
        ...

    def typed(self, name: str, expected: type[T]) -> T:
        ...

    def has(self, name: str) -> bool:
        ...


class Catalog(Tool):
    """
    Port: the objects of the workspace. `add` raises ConflictError if the
    id is taken; `update`, `remove` and the thumbnail methods raise
    NotFoundError for an unknown id. `children` returns the objects that
    list `object_id` among their parents. Thumbnails are SVG markup.
    """

    name = CATALOG_TOOL

    @abstractmethod
    def add(self, obj: ObjectRef) -> None:
        raise NotImplementedError

    @abstractmethod
    def get(self, object_id: str) -> ObjectRef | None:
        raise NotImplementedError

    @abstractmethod
    def list(self) -> builtins.list[ObjectRef]:
        raise NotImplementedError

    @abstractmethod
    def children(self, object_id: str) -> builtins.list[ObjectRef]:
        raise NotImplementedError

    @abstractmethod
    def update(self, obj: ObjectRef) -> None:
        raise NotImplementedError

    @abstractmethod
    def remove(self, object_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_thumbnail(self, object_id: str) -> str | None:
        raise NotImplementedError

    @abstractmethod
    def set_thumbnail(self, object_id: str, svg: str | None) -> None:
        raise NotImplementedError


class Preferences(Tool):
    """Port: user preferences, a flat key -> JSON-serializable value store."""

    name = PREFERENCES_TOOL

    @abstractmethod
    def get(self, key: str) -> Any:
        """The stored value, or None if `key` was never set."""
        raise NotImplementedError

    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        raise NotImplementedError
