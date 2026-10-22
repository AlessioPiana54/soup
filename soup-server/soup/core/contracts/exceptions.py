"""
------------------------------------------------------------------------
File : exceptions.py
Description: Domain exceptions of the plugin system. These are contracts
             in their own right: both the host (PluginManager, Registry)
             and plugins can raise/catch them without depending on any
             concrete implementation.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from typing import Iterable


class PluginError(Exception):
    """Base class for every error raised by the plugin system."""


class PluginConflictError(PluginError):
    """
    Raised by Registry.register() when two plugins try to register the
    same key for the same kind of contribution. Always names both the
    plugin that owns the existing registration and the one that tried to
    overwrite it.
    """

    def __init__(self, kind: str, key: str, existing_owner: str, new_owner: str):
        self.kind = kind
        self.key = key
        self.existing_owner = existing_owner
        self.new_owner = new_owner
        super().__init__(
            f"Conflict registering '{key}' ({kind}): already registered by "
            f"plugin '{existing_owner}', cannot be re-registered by plugin '{new_owner}'"
        )


class PluginCycleError(PluginError):
    """Raised when a dependency cycle is found among plugins' `requires`."""

    def __init__(self, cycle: Iterable[str]):
        self.cycle = list(cycle)
        super().__init__("Dependency cycle detected among plugins: " + " -> ".join(self.cycle))


class PluginDependencyError(PluginError):
    """Raised when a plugin declares a `requires` dependency that is not available."""

    def __init__(self, plugin_name: str, missing: Iterable[str]):
        self.plugin_name = plugin_name
        self.missing = list(missing)
        super().__init__(
            f"Plugin '{plugin_name}' requires missing/unavailable dependencies: "
            f"{', '.join(self.missing)}"
        )


class PluginApiVersionError(PluginError):
    """Raised when a plugin's declared api_version is incompatible with the host's."""

    def __init__(self, plugin_name: str, plugin_api_version: str, host_api_version: str):
        self.plugin_name = plugin_name
        self.plugin_api_version = plugin_api_version
        self.host_api_version = host_api_version
        super().__init__(
            f"Plugin '{plugin_name}' requires contracts api_version "
            f"'{plugin_api_version}', host provides '{host_api_version}'"
        )


class PluginMissingToolsError(PluginError):
    """Raised when a package declares `requires_tools` that no loaded package provides."""

    def __init__(self, plugin_name: str, missing: Iterable[str]):
        self.plugin_name = plugin_name
        self.missing = list(missing)
        super().__init__(
            f"Plugin '{plugin_name}' requires tools that no loaded package provides: "
            f"{', '.join(self.missing)}"
        )


class ToolNotDeclaredError(PluginError):
    """
    Raised when a package (or one of its contributions) uses or adds a
    tool it did not declare - in requires_tools to use it, in
    provides_tools to add it.
    """

    def __init__(self, owner: str, tool_name: str, declaration: str = "requires_tools"):
        self.owner = owner
        self.tool_name = tool_name
        self.declaration = declaration
        super().__init__(f"'{owner}' did not declare tool '{tool_name}' in {declaration}")


class ExtensionPointError(PluginError):
    """Raised when contributing to, or reading, an extension point that does not exist."""
