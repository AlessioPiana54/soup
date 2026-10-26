"""
------------------------------------------------------------------------
File : system_service.py
Description: SystemService - the state of the server as the API reports
             it, computed at each request (packages are enabled and
             disabled at runtime): the loaded tools with their package
             and health(), and an overall health that is "degraded" when
             a tool is not ok, a core tool is missing or a package failed
             to load. A tool whose health() raises (it must not) is
             reported as not ok instead of breaking the answer. Also the
             user preferences, through the "preferences" tool, with keys
             validated like any user-chosen name.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from soup.core.contracts import Tool, validate_name
from soup.core.packages import STATUS_FAILED, PackageManager
from soup.core.registry import Registry
from soup.core.services.core_tools import CoreTools, missing_core_tools

_LOGGER = logging.getLogger("soup.system")

HEALTH_OK = "ok"
HEALTH_DEGRADED = "degraded"


@dataclass(frozen=True)
class ToolStatus:
    name: str
    package: str
    health: dict[str, Any]

    @property
    def ok(self) -> bool:
        return bool(self.health.get("ok"))


@dataclass(frozen=True)
class Health:
    status: str
    tools: list[ToolStatus] = field(default_factory=list)
    # Human-readable problems: missing core tools, failed packages.
    problems: list[str] = field(default_factory=list)


class SystemService:
    def __init__(self, tools: Registry[Tool], core_tools: CoreTools, packages: PackageManager):
        self._tools = tools
        self._core_tools = core_tools
        self._packages = packages

    def tools(self) -> list[ToolStatus]:
        return [ToolStatus(entry.key, entry.package, _health_of(entry.item)) for entry in sorted(
            self._tools.entries(), key=lambda entry: entry.key
        )]

    def health(self) -> Health:
        tools = self.tools()
        problems = list(missing_core_tools(self._tools))
        problems.extend(
            f"Package '{info.name}' failed to load: {info.error}"
            for info in self._packages.list() if info.status == STATUS_FAILED
        )
        problems.extend(
            f"Tool '{tool.name}' is not healthy: {tool.health.get('error') or 'no details'}"
            for tool in tools if not tool.ok
        )
        return Health(HEALTH_DEGRADED if problems else HEALTH_OK, tools, problems)

    def get_preference(self, key: str) -> Any:
        """The stored value, None if never set. :raises ServiceUnavailableError: no preferences tool"""

        validate_name(key, label="Preference key")
        return self._core_tools.preferences().get(key)

    def set_preference(self, key: str, value: Any) -> None:
        validate_name(key, label="Preference key")
        self._core_tools.preferences().set(key, value)


def _health_of(tool: Tool) -> dict[str, Any]:
    try:
        health = tool.health()
    except Exception as exc:  # noqa: BLE001 - health() must not raise; report it instead
        _LOGGER.exception("Tool '%s'.health() raised", tool.name)
        return {"ok": False, "error": f"health() raised {type(exc).__name__}: {exc}"}
    if not isinstance(health, dict):
        return {"ok": False, "error": f"health() returned {type(health).__name__}, not a dict"}
    return dict(health)
