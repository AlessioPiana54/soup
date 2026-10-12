"""
------------------------------------------------------------------------
File : plugin_manager.py
Description: Discovers, orders, loads and shuts down plugins. Mirrors the
             six-phase lifecycle from the refactoring document:
             1. Discovery   - SOUP_PLUGINS env var + "soup.plugins" entry points
             2. Ordering    - topological sort on `requires`, cycle detection
             3. Verification- required deps present, api_version compatible
             4. Registration- calls register(ctx); PluginContext attributes
                               every contribution to the current plugin
             5. Isolation   - a failing plugin is excluded and recorded in
                               the PluginReport; the host still starts
                               (unless `strict=True`)
             6. Shutdown    - on_shutdown(ctx) in reverse load order
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import importlib
import importlib.metadata as importlib_metadata
import os
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

from soup.core.contracts import (
    CONTRACTS_API_VERSION,
    PluginApiVersionError,
    PluginCycleError,
    PluginDependencyError,
    SoupPlugin,
)
from soup.core.plugin_context import DefaultPluginContext

ENTRY_POINT_GROUP = "soup.plugins"
ENV_VAR = "SOUP_PLUGINS"


@dataclass
class PluginFailure:
    plugin_name: str
    error: Exception


@dataclass
class PluginReport:
    """Outcome of a PluginManager.load() call: who loaded, who did not and why."""

    loaded: list[str] = field(default_factory=list)
    failed: list[PluginFailure] = field(default_factory=list)

    def add_loaded(self, name: str) -> None:
        self.loaded.append(name)

    def add_failure(self, name: str, error: Exception) -> None:
        self.failed.append(PluginFailure(name, error))

    @property
    def has_failures(self) -> bool:
        return bool(self.failed)


class PluginManager:
    def __init__(self, contracts_api_version: str = CONTRACTS_API_VERSION, strict: bool = False):
        self.contracts_api_version = contracts_api_version
        self.strict = strict
        self.report: PluginReport = PluginReport()
        self._ctx: Optional[DefaultPluginContext] = None
        self._loaded_plugins: list[SoupPlugin] = []

    # ------------------------------------------------------------------ #
    # Phase 1: discovery
    # ------------------------------------------------------------------ #
    def discover(self, specs: Optional[Iterable[Any]] = None) -> list[SoupPlugin]:
        """
        Resolve `specs` into SoupPlugin instances, without registering
        them. Each spec may be a SoupPlugin instance, a SoupPlugin
        subclass, or a string (either the name of a "soup.plugins" entry
        point, or a dotted "module.path:Attribute" spec).

        If `specs` is None, reads short names from the SOUP_PLUGINS
        environment variable (comma-separated) and resolves each one
        against the "soup.plugins" entry points first, falling back to
        treating it as a dotted module path.
        """

        entry_points: dict[str, Any] = {}
        if specs is None:
            specs = self._specs_from_env()
            entry_points = self._entry_point_lookup()

        return [self._resolve_spec(spec, entry_points) for spec in specs]

    @staticmethod
    def _specs_from_env() -> list[str]:
        raw = os.environ.get(ENV_VAR, "")
        return [item.strip() for item in raw.split(",") if item.strip()]

    @staticmethod
    def _entry_point_lookup() -> dict[str, Any]:
        eps = importlib_metadata.entry_points(group=ENTRY_POINT_GROUP)
        return {ep.name: ep for ep in eps}

    def _resolve_spec(self, spec: Any, entry_points: Optional[dict[str, Any]] = None) -> SoupPlugin:
        entry_points = entry_points or {}

        if isinstance(spec, SoupPlugin):
            return spec
        if isinstance(spec, type) and issubclass(spec, SoupPlugin):
            return spec()
        if isinstance(spec, str):
            if spec in entry_points:
                return self._resolve_spec(entry_points[spec].load())
            return self._load_dotted_path(spec)

        raise TypeError(f"Unsupported plugin spec: {spec!r}")

    def _load_dotted_path(self, dotted: str) -> SoupPlugin:
        module_path, _, attr = dotted.partition(":")
        module = importlib.import_module(module_path)
        obj = getattr(module, attr) if attr else (
            getattr(module, "PLUGIN", None) or getattr(module, "plugin", None)
        )
        if obj is None:
            raise ImportError(f"Cannot resolve a SoupPlugin from spec '{dotted}'")
        return self._resolve_spec(obj)

    # ------------------------------------------------------------------ #
    # Phases 2-5: ordering, verification, registration, isolation
    # ------------------------------------------------------------------ #
    def load(self, plugins: Iterable[SoupPlugin], ctx: Optional[DefaultPluginContext] = None) -> PluginReport:
        ctx = ctx if ctx is not None else DefaultPluginContext()
        self._ctx = ctx

        plugins = list(plugins)
        by_name = {plugin.name: plugin for plugin in plugins}
        report = PluginReport()

        valid = self._verify(plugins, by_name, report)
        ordered = self._topological_order(valid)  # raises PluginCycleError, not isolated

        self._loaded_plugins = []
        for plugin in ordered:
            try:
                ctx._set_current_plugin(plugin.name)
                plugin.register(ctx)
            except Exception as exc:  # noqa: BLE001 - isolate any plugin failure
                if self.strict:
                    raise
                report.add_failure(plugin.name, exc)
                continue
            else:
                report.add_loaded(plugin.name)
                self._loaded_plugins.append(plugin)
            finally:
                ctx._set_current_plugin(None)

        self.report = report
        return report

    def _verify(self, plugins: list[SoupPlugin], by_name: dict[str, SoupPlugin], report: PluginReport) -> list[SoupPlugin]:
        """
        Phase 3: exclude (and record in `report`) plugins with an
        incompatible api_version or with `requires` dependencies that are
        missing entirely or that themselves failed verification
        (computed to a fixpoint so cascading failures are also isolated).
        """

        candidates = dict(by_name)
        failed_names: set[str] = set()

        changed = True
        while changed:
            changed = False
            for name, plugin in list(candidates.items()):
                if plugin.api_version != self.contracts_api_version:
                    self._fail(report, name, PluginApiVersionError(name, plugin.api_version, self.contracts_api_version))
                    del candidates[name]
                    failed_names.add(name)
                    changed = True
                    continue

                missing = [dep for dep in plugin.requires if dep not in by_name]
                unavailable = [dep for dep in plugin.requires if dep in failed_names and dep not in missing]
                all_missing = missing + unavailable
                if all_missing:
                    self._fail(report, name, PluginDependencyError(name, all_missing))
                    del candidates[name]
                    failed_names.add(name)
                    changed = True
                    continue

        return [plugins_by_original_order for plugins_by_original_order in plugins if plugins_by_original_order.name in candidates]

    def _fail(self, report: PluginReport, name: str, error: Exception) -> None:
        if self.strict:
            raise error
        report.add_failure(name, error)

    @staticmethod
    def _topological_order(plugins: list[SoupPlugin]) -> list[SoupPlugin]:
        by_name = {plugin.name: plugin for plugin in plugins}
        order_index = {plugin.name: i for i, plugin in enumerate(plugins)}
        indegree = {plugin.name: 0 for plugin in plugins}
        dependents: dict[str, list[str]] = {plugin.name: [] for plugin in plugins}

        for plugin in plugins:
            for dep in plugin.requires:
                if dep in by_name:
                    dependents[dep].append(plugin.name)
                    indegree[plugin.name] += 1

        queue = sorted((name for name, deg in indegree.items() if deg == 0), key=lambda n: order_index[n])
        result: list[SoupPlugin] = []
        visited: set[str] = set()

        while queue:
            queue.sort(key=lambda n: order_index[n])
            name = queue.pop(0)
            result.append(by_name[name])
            visited.add(name)
            for dependent in dependents[name]:
                indegree[dependent] -= 1
                if indegree[dependent] == 0:
                    queue.append(dependent)

        if len(result) != len(plugins):
            remaining = [plugin.name for plugin in plugins if plugin.name not in visited]
            raise PluginCycleError(remaining)

        return result

    # ------------------------------------------------------------------ #
    # Phase 6: shutdown
    # ------------------------------------------------------------------ #
    def shutdown(self) -> None:
        if self._ctx is None:
            return
        for plugin in reversed(self._loaded_plugins):
            try:
                plugin.on_shutdown(self._ctx)
            except Exception:  # noqa: BLE001 - shutdown is best-effort
                pass
