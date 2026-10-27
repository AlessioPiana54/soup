"""
------------------------------------------------------------------------
File : runtime.py
Description: EkgRuntime - what the module-level functions of api.py
             (build_ekg, ensure_loaded, dispose) need of the active ekg
             package: its own tools (the catalog, to walk an object's
             parents), the EventBus (ekg.before_reset, ekg.built) and the
             contributions to its two extension points. The Plugin
             activates one in register() and deactivates it on shutdown;
             with the package disabled the functions answer 503.
Project : soup-packages/ekg
------------------------------------------------------------------------
"""

from __future__ import annotations

import threading
from typing import Any, Mapping, Optional

from soup.core.contracts import PluginContext, ServiceUnavailableError, ToolAccess

# Extension points this package opens (declared in soup-package.json).
BUILD_STEPS_POINT = "ekg.build_steps"
STATE_PROVIDERS_POINT = "ekg.state_providers"


class EkgRuntime:
    def __init__(self, ctx: PluginContext):
        self._ctx = ctx
        # Captured during register(): the tools this package declared.
        self.tools: ToolAccess = ctx.tools

    def publish(self, event: str, payload: Mapping[str, Any]) -> None:
        self._ctx.publish(event, payload)

    def build_steps(self) -> list[Any]:
        return self._ctx.contributions(BUILD_STEPS_POINT)

    def state_provider(self, key: str) -> Any:
        """:raises ServiceUnavailableError: no active package contributes provider `key`"""

        for provider in self._ctx.contributions(STATE_PROVIDERS_POINT):
            if getattr(provider, "key", None) == key:
                return provider
        raise ServiceUnavailableError(f"No active package provides the EKG state '{key}'")


_lock = threading.Lock()
_current: Optional[EkgRuntime] = None


def activate(runtime: EkgRuntime) -> None:
    global _current
    with _lock:
        _current = runtime


def deactivate(runtime: EkgRuntime) -> None:
    global _current
    with _lock:
        if _current is runtime:
            _current = None


def current() -> EkgRuntime:
    """:raises ServiceUnavailableError: the ekg package is not active"""

    runtime = _current
    if runtime is None:
        raise ServiceUnavailableError("The ekg package is not active")
    return runtime
