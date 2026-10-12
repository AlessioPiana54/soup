"""
------------------------------------------------------------------------
File : plugin.py
Description: SoupPlugin (the interface every plugin implements) and
             PluginContext (the facade the host offers to plugins during
             registration, so they contribute to the host's registries
             without ever importing the host's concrete implementation).
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Protocol, Sequence

from soup.core.contracts.version import CONTRACTS_API_VERSION


class PluginContext(Protocol):
    """
    Facade offered to a plugin's register(ctx) call. Every add_* call
    attributes the contribution to the plugin currently being registered -
    the plugin never passes its own name.
    """

    def add_input_reader(self, key: str, reader: Any) -> None:
        ...

    def add_input_handler(self, key: str, handler: Any) -> None:
        ...

    def add_build_step(self, key: str, step: Any) -> None:
        ...


class SoupPlugin(ABC):
    """
    Base interface every plugin implements. `name` must be unique among
    loaded plugins; `requires` lists the names of plugins that must load
    (successfully) before this one; `api_version` must match the host's
    soup.core.contracts.CONTRACTS_API_VERSION.
    """

    name: str = ""
    version: str = "0.0.0"
    requires: Sequence[str] = ()
    api_version: str = CONTRACTS_API_VERSION

    @abstractmethod
    def register(self, ctx: PluginContext) -> None:
        """Contribute this plugin's readers/handlers/build steps to `ctx`."""
        raise NotImplementedError

    def on_shutdown(self, ctx: PluginContext) -> None:
        """Optional cleanup hook, called in reverse load order. No-op by default."""
        return None
