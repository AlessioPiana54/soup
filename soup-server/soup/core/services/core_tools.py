"""
------------------------------------------------------------------------
File : core_tools.py
Description: CoreTools - how the core's own services reach the tools
             they depend on (the Catalog and Preferences ports, provided
             by packages), resolve object ids through the catalog and
             build the ToolBox handed to each contribution. A missing
             core tool is not a startup error: the services that need it
             answer 503 with a clear message. The legacy import path
             also reaches the "memgraph" and "storage" tools by name
             (graph(), storage(); TODO(commit 8): it moves to the ekg
             package, which declares them in requires_tools).
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Callable, Iterable, TypeVar, Union

from soup.core.contracts import (
    CATALOG_TOOL,
    PREFERENCES_TOOL,
    Catalog,
    GraphDatabase,
    NotFoundError,
    ObjectRef,
    Preferences,
    ServiceUnavailableError,
    Tool,
    ValidationError,
)
from soup.core.process_timer import DATE_FORMAT
from soup.core.registry import Registry
from soup.core.toolbox import ToolBox

T = TypeVar("T", bound=Tool)

ObjectLike = Union[ObjectRef, str]

# Core tools: (name, port) pairs that build_engine checks after loading
# the packages, so a missing one is reported in the PluginReport.
CORE_TOOLS: tuple[tuple[str, type[Tool]], ...] = (
    (CATALOG_TOOL, Catalog),
    (PREFERENCES_TOOL, Preferences),
)

# Tools the legacy import path reaches by name (TODO(commit 8): drop,
# with the legacy path). Provided by tool_memgraph and tool_storage.
MEMGRAPH_TOOL = "memgraph"
STORAGE_TOOL = "storage"
_STORAGE_METHODS = ("space", "path_for", "delete_space")
LEGACY_TOOLS: tuple[tuple[str, str], ...] = (
    (MEMGRAPH_TOOL, "/api/v2/graph and /api/v2/memgraph-connect"),
    (STORAGE_TOOL, "/api/v2/graph"),
)


def new_object_id() -> str:
    return str(uuid.uuid4())


def timestamp(clock: Callable[[], datetime]) -> str:
    """Same format as ProcessTimer: "2025-01-01T10:00:00.123"."""

    return clock().strftime(DATE_FORMAT)[:-3]


def check_object_id(object_id: Any) -> str:
    """Object ids are uuids assigned by the core; anything else is refused (400)."""

    if not isinstance(object_id, str):
        raise ValidationError(f"Invalid object id: {object_id!r}")
    try:
        uuid.UUID(object_id)
    except ValueError:
        raise ValidationError(f"Invalid object id: {object_id!r}") from None
    return object_id


class CoreTools:
    def __init__(self, tools: Registry[Tool]):
        self._tools = tools

    def catalog(self) -> Catalog:
        return self._port(CATALOG_TOOL, Catalog, "the object catalog")

    def preferences(self) -> Preferences:
        return self._port(PREFERENCES_TOOL, Preferences, "user preferences")

    def graph(self) -> GraphDatabase:
        """The "memgraph" tool, for the legacy import path. :raises ServiceUnavailableError:"""

        tool = self._tools.get(MEMGRAPH_TOOL)
        if tool is None:
            raise ServiceUnavailableError(
                f"The graph database is not available: no loaded package provides the '{MEMGRAPH_TOOL}' tool"
            )
        if not isinstance(tool, GraphDatabase):
            raise ServiceUnavailableError(
                f"The graph database is not available: the '{MEMGRAPH_TOOL}' tool is a "
                f"{type(tool).__name__}, not a GraphDatabase"
            )
        return tool

    def storage(self) -> Tool:
        """The "storage" tool, for the legacy import path. :raises ServiceUnavailableError:"""

        tool = self._tools.get(STORAGE_TOOL)
        if tool is None:
            raise ServiceUnavailableError(
                f"File storage is not available: no loaded package provides the '{STORAGE_TOOL}' tool"
            )
        missing = [method for method in _STORAGE_METHODS if not callable(getattr(tool, method, None))]
        if missing:
            raise ServiceUnavailableError(
                f"File storage is not available: the '{STORAGE_TOOL}' tool has no {', '.join(missing)}"
            )
        return tool

    def object(self, obj: ObjectLike) -> ObjectRef:
        """Resolve an id (or pass an ObjectRef through). :raises NotFoundError:"""

        if isinstance(obj, ObjectRef):
            return obj
        ref = self.catalog().get(check_object_id(obj))
        if ref is None:
            raise NotFoundError(f"Object '{obj}' not found")
        return ref

    def available(self, names: Iterable[str]) -> bool:
        return all(name in self._tools for name in names)

    def toolbox(self, owner: str, requires_tools: Iterable[str]) -> ToolBox:
        return ToolBox(self._tools, tuple(requires_tools or ()), owner)

    def _port(self, name: str, port: type[T], what: str) -> T:
        tool = self._tools.get(name)
        if tool is None:
            raise ServiceUnavailableError(
                f"{what.capitalize()} is not available: no loaded package provides the '{name}' tool"
            )
        if not isinstance(tool, port):
            raise ServiceUnavailableError(
                f"{what.capitalize()} is not available: the '{name}' tool is a "
                f"{type(tool).__name__}, not a {port.__name__}"
            )
        return tool


def missing_core_tools(tools: Registry[Tool]) -> list[str]:
    """Human-readable problems with the core tools, for the PluginReport."""

    problems = []
    for name, port in CORE_TOOLS:
        tool = tools.get(name)
        if tool is None:
            problems.append(f"No package provides the '{name}' tool: services that need it will answer 503")
        elif not isinstance(tool, port):
            problems.append(
                f"The '{name}' tool is a {type(tool).__name__}, not a {port.__name__}: "
                "services that need it will answer 503"
            )
    for name, routes in LEGACY_TOOLS:
        if name not in tools:
            problems.append(f"No package provides the '{name}' tool: {routes} will answer 503")
    return problems


def kinds_of(value: Any) -> tuple[str, ...]:
    """A contribution's `accepts`, whether declared as one kind or several."""

    return (value,) if isinstance(value, str) else tuple(value or ())
