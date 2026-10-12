"""
------------------------------------------------------------------------
File : plugin_context.py
Description: Concrete, host-side implementation of the PluginContext
             facade (soup.core.contracts.PluginContext) handed to each
             plugin's register(ctx) call.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from typing import Any, Optional

from soup.core.registry import Registry


class DefaultPluginContext:
    """
    Holds the host's extension registries and attributes every
    contribution to whichever plugin is currently being registered.
    `PluginManager` sets/clears the current plugin around each call to
    plugin.register(ctx); plugins never pass their own name.
    """

    def __init__(self) -> None:
        self.input_readers: Registry[Any] = Registry("input_reader")
        self.input_handlers: Registry[Any] = Registry("input_handler")
        self.build_steps: Registry[Any] = Registry("build_step")
        self._current_plugin: Optional[str] = None

    # --- used internally by PluginManager; not part of the plugin-facing API ---
    def _set_current_plugin(self, name: Optional[str]) -> None:
        self._current_plugin = name

    def _require_current_plugin(self) -> str:
        if self._current_plugin is None:
            raise RuntimeError("No plugin is currently being registered")
        return self._current_plugin

    # --- contributions API exposed to plugins (soup.core.contracts.PluginContext) ---
    def add_input_reader(self, key: str, reader: Any) -> None:
        self.input_readers.register(reader, self._require_current_plugin(), key)

    def add_input_handler(self, key: str, handler: Any) -> None:
        self.input_handlers.register(handler, self._require_current_plugin(), key)

    def add_build_step(self, key: str, step: Any) -> None:
        self.build_steps.register(step, self._require_current_plugin(), key)
