"""
------------------------------------------------------------------------
File : plugin.py
Description: SoupPlugin (the interface every package implements) and
             PluginContext (the facade the host offers to packages during
             registration, so they contribute to the host's registries
             without ever importing the host's concrete implementation).
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Mapping, Protocol, Sequence

from soup.core.contracts.version import CONTRACTS_API_VERSION

EventHandler = Callable[[Mapping[str, Any]], None]


class PluginContext(Protocol):
    """
    Facade offered to a package's register(ctx) call. Every add_* call
    attributes the contribution to the package currently being
    registered - the package never passes its own name. Duplicate keys
    raise PluginConflictError naming both packages.

    - add_importer / add_operation / add_visualizer / add_exporter /
      add_tool: keyed by the contribution's id (a tool by its name). A
      tool must be declared in the package's provides_tools; any other
      contribution may only require tools the package requires or
      provides. `tools` gives the package access to those same tools.
    - add_extension_point(name) opens a point other packages (which list
      this one in `requires`) contribute to with contribute(); the owner
      reads them with contributions(), ordered by `order` then by
      registration.
    - subscribe(event, handler, critical) / publish(event, payload): the
      EventBus. The core publishes only its lifecycle events
      (soup/core/events.py); domain events are constants declared by the
      publishing package in its api.py. A failing handler is logged and
      does not stop the others, unless it subscribed as critical: then
      its error propagates to the publisher.
    """

    @property
    def tools(self) -> Any:
        ...

    def add_input_reader(self, key: str, reader: Any) -> None:
        ...

    def add_input_handler(self, key: str, handler: Any) -> None:
        ...

    def add_build_step(self, key: str, step: Any) -> None:
        ...

    def add_importer(self, importer: Any) -> None:
        ...

    def add_operation(self, operation: Any) -> None:
        ...

    def add_visualizer(self, visualizer: Any) -> None:
        ...

    def add_exporter(self, exporter: Any) -> None:
        ...

    def add_tool(self, tool: Any) -> None:
        ...

    def add_extension_point(self, name: str) -> None:
        ...

    def contribute(self, point: str, item: Any, key: str, order: int = 0) -> None:
        ...

    def contributions(self, point: str) -> list[Any]:
        ...

    def subscribe(self, event: str, handler: EventHandler, critical: bool = False) -> None:
        ...

    def publish(self, event: str, payload: Mapping[str, Any]) -> None:
        ...


class SoupPlugin(ABC):
    """
    Base interface every package implements. `name` must be unique among
    loaded packages; `requires` lists the names of packages that must
    load (successfully) before this one; `requires_tools` lists the tools
    it uses and `provides_tools` the tools it adds (a package loads after
    the providers of its tools, and is dropped if one is missing);
    `api_version` must match the host's
    soup.core.contracts.CONTRACTS_API_VERSION.
    """

    name: str = ""
    version: str = "0.0.0"
    requires: Sequence[str] = ()
    requires_tools: Sequence[str] = ()
    provides_tools: Sequence[str] = ()
    api_version: str = CONTRACTS_API_VERSION

    @abstractmethod
    def register(self, ctx: PluginContext) -> None:
        """Contribute this package's importers/operations/visualizers/... to `ctx`."""
        raise NotImplementedError

    def on_shutdown(self, ctx: PluginContext) -> None:
        """Optional cleanup hook, called in reverse load order. No-op by default."""
        return None
