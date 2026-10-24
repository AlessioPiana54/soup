"""
------------------------------------------------------------------------
File : plugin_manager.py
Description: Orders, loads, unloads and shuts down plugins (the SoupPlugin
             of each package). Packages are found on disk by the
             PackageManager (soup/core/packages), which hands their
             plugins to this class; discover() only resolves specs
             passed in code (tests, "soup.plugins" entry points).
             Mirrors the six-phase lifecycle from the refactoring document:
             1. Discovery   - explicit specs + "soup.plugins" entry points
             2. Ordering    - topological sort on `requires` and on tools
                               (a tool's provider loads before the
                               packages requiring it), cycle detection
             3. Verification- required deps and required tools present,
                               api_version compatible (same major,
                               minor not above the host's)
             4. Registration- calls register(ctx); PluginContext attributes
                               every contribution to the current plugin;
                               "package.loaded" is published on success
             5. Isolation   - a failing plugin is excluded, its partial
                               contributions removed (remove_owner) and
                               the reason recorded in the PackageReport;
                               the host still starts (unless `strict=True`)
             6. Shutdown    - on_shutdown(ctx) in reverse load order, then
                               "package.unloaded"
             load() is incremental: packages loaded by an earlier call
             satisfy the `requires` of later ones (runtime install and
             enable), and unload() removes one package at runtime.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import importlib
import importlib.metadata as importlib_metadata
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

from soup.core.contracts import (
    CONTRACTS_API_VERSION,
    is_api_compatible,
    PluginApiVersionError,
    PluginCycleError,
    PluginDependencyError,
    PluginError,
    PluginMissingToolsError,
    SoupPlugin,
)
from soup.core.events import PACKAGE_LOADED, PACKAGE_UNLOADED
from soup.core.plugin_context import DefaultPluginContext

ENTRY_POINT_GROUP = "soup.plugins"


@dataclass
class PluginFailure:
    plugin_name: str
    error: Exception

    @property
    def reason(self) -> str:
        return str(self.error)


@dataclass
class PackageReport:
    """
    Outcome of loading packages: who loaded, who was left disabled (by
    the persisted state or the SOUP_PACKAGES override), who did not load
    and why.
    """

    loaded: list[str] = field(default_factory=list)
    failed: list[PluginFailure] = field(default_factory=list)
    disabled: list[str] = field(default_factory=list)
    # Problems that exclude no package but leave a service unable to
    # answer (e.g. no package provides the object catalog).
    warnings: list[str] = field(default_factory=list)

    def add_loaded(self, name: str) -> None:
        self.loaded.append(name)

    def add_failure(self, name: str, error: Exception) -> None:
        self.failed.append(PluginFailure(name, error))

    def add_disabled(self, name: str) -> None:
        self.disabled.append(name)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)

    def merge(self, other: "PackageReport") -> None:
        self.loaded.extend(other.loaded)
        self.failed.extend(other.failed)
        self.disabled.extend(other.disabled)
        self.warnings.extend(other.warnings)

    @property
    def has_failures(self) -> bool:
        return bool(self.failed)


# TODO(commit 11): remove the old name once nothing imports it.
PluginReport = PackageReport


class PluginManager:
    def __init__(self, contracts_api_version: str = CONTRACTS_API_VERSION, strict: bool = False):
        self.contracts_api_version = contracts_api_version
        self.strict = strict
        self.report: PackageReport = PackageReport()
        self._ctx: Optional[DefaultPluginContext] = None
        # Replaced, never mutated: readers (package_status, list) iterate a snapshot.
        self._loaded_plugins: tuple[SoupPlugin, ...] = ()

    # ------------------------------------------------------------------ #
    # Phase 1: discovery
    # ------------------------------------------------------------------ #
    def discover(self, specs: Optional[Iterable[Any]] = None) -> list[SoupPlugin]:
        """
        Resolve `specs` into SoupPlugin instances, without registering
        them. Each spec may be a SoupPlugin instance, a SoupPlugin
        subclass, or a string: the name of a "soup.plugins" entry point,
        or a dotted "module.path:Attribute" spec. Packages on disk are
        not resolved here: the PackageManager loads them.
        """

        entry_points = self._entry_point_lookup()
        return [self._resolve_spec(spec, entry_points) for spec in specs or ()]

    @staticmethod
    def _entry_point_lookup() -> dict[str, Any]:
        eps = importlib_metadata.entry_points(group=ENTRY_POINT_GROUP)
        return {ep.name: ep for ep in eps}

    def _resolve_spec(self, spec: Any, entry_points: Optional[dict[str, Any]] = None) -> SoupPlugin:
        entry_points = entry_points if entry_points is not None else self._entry_point_lookup()

        if isinstance(spec, SoupPlugin):
            return spec
        if isinstance(spec, type) and issubclass(spec, SoupPlugin):
            return spec()
        if isinstance(spec, str):
            if spec in entry_points:
                return self._resolve_spec(entry_points[spec].load(), entry_points)
            return self._load_dotted_path(spec, entry_points)

        raise TypeError(f"Unsupported plugin spec: {spec!r}")

    def _load_dotted_path(self, dotted: str, entry_points: Optional[dict[str, Any]] = None) -> SoupPlugin:
        module_path, _, attr = dotted.partition(":")
        try:
            module = importlib.import_module(module_path)
        except ImportError as exc:
            raise ImportError(f"Cannot resolve a SoupPlugin from spec '{dotted}'") from exc

        obj = getattr(module, attr, None) if attr else (
            getattr(module, "PLUGIN", None) or getattr(module, "plugin", None)
        )
        if obj is None:
            raise ImportError(f"Cannot resolve a SoupPlugin from spec '{dotted}'")
        return self._resolve_spec(obj, entry_points)

    # ------------------------------------------------------------------ #
    # Phases 2-5: ordering, verification, registration, isolation
    # ------------------------------------------------------------------ #
    @property
    def loaded_names(self) -> list[str]:
        return [plugin.name for plugin in self._loaded_plugins]

    def get(self, name: str) -> Optional[SoupPlugin]:
        return next((plugin for plugin in self._loaded_plugins if plugin.name == name), None)

    def load(self, plugins: Iterable[SoupPlugin], ctx: Optional[DefaultPluginContext] = None) -> PackageReport:
        """
        Load `plugins` into `ctx` (by default the context of the previous
        call, or a new one). Packages already loaded into the same
        context stay loaded and satisfy the `requires` of the new ones.
        Returns the report of this call; self.report accumulates them.
        """

        ctx = ctx if ctx is not None else (self._ctx or DefaultPluginContext())
        if ctx is not self._ctx:
            self._ctx = ctx
            self._loaded_plugins = ()
            self.report = PackageReport()

        report = PackageReport()
        already_loaded = set(self.loaded_names)
        plugins = list(plugins)
        for plugin in [plugin for plugin in plugins if plugin.name in already_loaded]:
            self._fail(report, plugin.name, PluginError(f"Package '{plugin.name}' is already loaded"))
            plugins.remove(plugin)

        by_name = {plugin.name: plugin for plugin in plugins}
        # Tools registered by the host, or by packages already loaded, count as provided.
        host_tools = set(ctx.tool_registry.keys())

        valid = self._verify(plugins, by_name, report, host_tools, already_loaded)
        ordered = self._topological_order(valid)  # raises PluginCycleError, not isolated

        for plugin in ordered:
            # A provider that passed verification but then failed in
            # register() leaves its tools missing: its consumers fail here.
            missing_tools = [name for name in plugin.requires_tools if name not in ctx.tool_registry]
            if missing_tools:
                self._fail(report, plugin.name, PluginMissingToolsError(plugin.name, missing_tools))
                continue

            try:
                ctx._begin_plugin(plugin)
                plugin.register(ctx)
                not_added = [
                    name for name in plugin.provides_tools if ctx.tool_registry.owner_of(name) != plugin.name
                ]
                if not_added:
                    raise PluginError(
                        f"Plugin '{plugin.name}' declares provides_tools {not_added} but did not add them"
                    )
                points_not_added = [
                    name for name in plugin.extension_points
                    if name not in ctx.extension_points.points() or ctx.extension_points.owner_of(name) != plugin.name
                ]
                if points_not_added:
                    raise PluginError(
                        f"Plugin '{plugin.name}' declares extension_points {points_not_added} but did not open them"
                    )
            except Exception as exc:  # noqa: BLE001 - isolate any plugin failure
                ctx.remove_owner(plugin.name)
                if self.strict:
                    raise
                report.add_failure(plugin.name, exc)
                continue
            else:
                report.add_loaded(plugin.name)
                self._loaded_plugins = (*self._loaded_plugins, plugin)
            finally:
                ctx._end_plugin()
            ctx.publish(PACKAGE_LOADED, {"package": plugin.name, "version": plugin.version})

        self.report.merge(report)
        return report

    def unload(self, name: str) -> SoupPlugin:
        """
        Remove a loaded package at runtime: on_shutdown(ctx), then every
        contribution it made (registries, extension points,
        subscriptions), then "package.unloaded". Dependents are not
        checked here: the PackageManager refuses to unload a package
        that other loaded packages need.
        :raises KeyError: `name` is not loaded
        """

        plugin = self.get(name)
        if plugin is None or self._ctx is None:
            raise KeyError(name)
        try:
            plugin.on_shutdown(self._ctx)
        except Exception:  # noqa: BLE001 - the package's own cleanup is best-effort
            pass
        self._ctx.remove_owner(name)
        self._loaded_plugins = tuple(loaded for loaded in self._loaded_plugins if loaded is not plugin)
        self._ctx.publish(PACKAGE_UNLOADED, {"package": plugin.name, "version": plugin.version})
        return plugin

    def _verify(
        self,
        plugins: list[SoupPlugin],
        by_name: dict[str, SoupPlugin],
        report: PackageReport,
        host_tools: Optional[set[str]] = None,
        already_loaded: Optional[set[str]] = None,
    ) -> list[SoupPlugin]:
        """
        Phase 3: exclude (and record in `report`) plugins with an
        incompatible api_version, with `requires` dependencies that are
        missing entirely or that themselves failed verification, or with
        `requires_tools` that neither the host nor any remaining plugin
        provides (computed to a fixpoint so cascading failures are also
        isolated).
        """

        host_tools = host_tools or set()
        already_loaded = already_loaded or set()

        candidates = dict(by_name)
        failed_names: set[str] = set()

        changed = True
        while changed:
            changed = False
            for name, plugin in list(candidates.items()):
                if not is_api_compatible(plugin.api_version, self.contracts_api_version):
                    error = PluginApiVersionError(name, plugin.api_version, self.contracts_api_version)
                    self._fail(report, name, error)
                    del candidates[name]
                    failed_names.add(name)
                    changed = True
                    continue

                missing = [dep for dep in plugin.requires if dep not in by_name and dep not in already_loaded]
                unavailable = [dep for dep in plugin.requires if dep in failed_names and dep not in missing]
                all_missing = missing + unavailable
                if all_missing:
                    self._fail(report, name, PluginDependencyError(name, all_missing))
                    del candidates[name]
                    failed_names.add(name)
                    changed = True
                    continue

                provided = set(host_tools)
                for candidate in candidates.values():
                    provided.update(candidate.provides_tools)
                missing_tools = [tool for tool in plugin.requires_tools if tool not in provided]
                if missing_tools:
                    self._fail(report, name, PluginMissingToolsError(name, missing_tools))
                    del candidates[name]
                    failed_names.add(name)
                    changed = True
                    continue

        return [plugin for plugin in plugins if plugin.name in candidates]

    def _fail(self, report: PackageReport, name: str, error: Exception) -> None:
        if self.strict:
            raise error
        report.add_failure(name, error)

    @staticmethod
    def _topological_order(plugins: list[SoupPlugin]) -> list[SoupPlugin]:
        by_name = {plugin.name: plugin for plugin in plugins}
        order_index = {plugin.name: i for i, plugin in enumerate(plugins)}
        indegree = {plugin.name: 0 for plugin in plugins}
        dependents: dict[str, list[str]] = {plugin.name: [] for plugin in plugins}

        providers: dict[str, list[str]] = {}
        for plugin in plugins:
            for tool in plugin.provides_tools:
                providers.setdefault(tool, []).append(plugin.name)

        for plugin in plugins:
            predecessors = [dep for dep in plugin.requires if dep in by_name]
            for tool in plugin.requires_tools:
                predecessors.extend(provider for provider in providers.get(tool, ()) if provider != plugin.name)
            for dep in dict.fromkeys(predecessors):
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
            try:
                self._ctx.publish(PACKAGE_UNLOADED, {"package": plugin.name, "version": plugin.version})
            except Exception:  # noqa: BLE001 - shutdown is best-effort
                pass
