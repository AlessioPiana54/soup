"""
------------------------------------------------------------------------
File : manager.py
Description: PackageManager - the runtime package lifecycle, on top of
             the PluginManager (which still registers/unregisters the
             SoupPlugin of each package):
             - load_all(): discovery from SOUP_PACKAGES_PATH, then the
               SOUP_PACKAGES override or the persisted enabled/disabled
               state, then checks made on the manifest BEFORE importing
               any code (api_version, python_dependencies, global names
               - tools and extension points - declared by two active
               packages, `requires`, dependency cycles), then import under soup_pkg_<name> and
               registration. Every failure is isolated in the
               PackageReport, unless strict.
             - install(zip) / uninstall(name): only if
               SOUP_ALLOW_PACKAGE_INSTALL is true (403 otherwise).
             - disable(name) / enable(name): Registry.remove_owner
               through PluginManager.unload, and registration of a fresh
               plugin instance; refused (409) while active packages
               depend on it, unless cascade.
             Objects created by a package that is no longer loaded stay
             in the catalog; package_status() tells the workspace whether
             their package is active, disabled or missing.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import logging
import os
import shutil
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO, Iterable, Optional

from soup.core.contracts import (
    CONTRACTS_API_VERSION,
    ConflictError,
    DomainError,
    ForbiddenError,
    NotFoundError,
    PluginApiVersionError,
    PluginConflictError,
    PluginCycleError,
    PluginDependencyError,
    PluginPythonDependencyError,
    SoupPlugin,
    ValidationError,
    is_api_compatible,
)
from soup.core.packages.archive import ArchiveLimits, extract_package_zip
from soup.core.packages.dependencies import VersionLookup, installed_version, python_dependency_problems
from soup.core.packages.discovery import ORIGIN_INSTALLED, PackageSource, discover_packages
from soup.core.packages.loader import PluginFactory, plugin_factory, purge
from soup.core.packages.manifest import PackageManifest, load_manifest, validate_package_name
from soup.core.packages.state import PackageState
from soup.core.plugin_context import DefaultPluginContext
from soup.core.plugin_manager import PackageReport, PluginManager

_LOGGER = logging.getLogger("soup.packages")

STATUS_ACTIVE = "active"
STATUS_DISABLED = "disabled"
STATUS_FAILED = "failed"
STATUS_MISSING = "missing"

STAGING_DIR = "_staging"


@dataclass(frozen=True)
class PackageInfo:
    name: str
    status: str
    version: str = ""
    label: str = ""
    description: str = ""
    author: str = ""
    origin: str = ""
    error: Optional[str] = None
    requires: tuple[str, ...] = ()
    requires_tools: tuple[str, ...] = ()
    provides_tools: tuple[str, ...] = ()
    extension_points: tuple[str, ...] = ()
    dependents: tuple[str, ...] = ()
    app_entry: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "version": self.version,
            "label": self.label,
            "description": self.description,
            "author": self.author,
            "origin": self.origin,
            "error": self.error,
            "requires": list(self.requires),
            "requires_tools": list(self.requires_tools),
            "provides_tools": list(self.provides_tools),
            "extension_points": list(self.extension_points),
            "dependents": list(self.dependents),
            "app_entry": self.app_entry,
        }


@dataclass
class PackageManagerConfig:
    packages_path: tuple[str, ...]
    installed_dir: str
    # None: every package found; otherwise only these (SOUP_PACKAGES).
    enabled_override: Optional[tuple[str, ...]] = None
    allow_install: bool = False
    strict: bool = False
    contracts_api_version: str = CONTRACTS_API_VERSION
    limits: ArchiveLimits = field(default_factory=ArchiveLimits)


class PackageManager:
    def __init__(
        self,
        plugin_manager: PluginManager,
        ctx: DefaultPluginContext,
        config: PackageManagerConfig,
        version_lookup: VersionLookup = installed_version,
    ):
        self.plugin_manager = plugin_manager
        self.ctx = ctx
        self.config = config
        self.installed_dir = Path(config.installed_dir)
        self.state = PackageState(self.installed_dir)
        self.report = PackageReport()
        self._version_lookup = version_lookup
        self._sources: dict[str, PackageSource] = {}
        self._factories: dict[str, PluginFactory] = {}
        self._errors: dict[str, str] = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------ #
    # Startup
    # ------------------------------------------------------------------ #
    def load_all(self, extra_plugins: Iterable[SoupPlugin] = ()) -> PackageReport:
        """
        Discover and load every enabled package, plus `extra_plugins`
        (plugins built in code, e.g. by tests). Returns the report.
        """

        with self._lock:
            report = PackageReport()
            discovery = discover_packages(self.config.packages_path, self.installed_dir)
            for warning in discovery.warnings:
                report.add_warning(warning)
            for folder, error in discovery.failures:
                self._fail(report, folder, error)
            self._sources = dict(discovery.sources)

            override = self.config.enabled_override
            if override is not None:
                for name in override:
                    if name not in self._sources:
                        report.add_warning(f"SOUP_PACKAGES lists '{name}', but no such package was found")

            candidates = []
            for name, source in self._sources.items():
                disabled = name not in override if override is not None else self.state.is_disabled(name)
                if disabled:
                    report.add_disabled(name)
                else:
                    candidates.append(source)

            plugins = self._prepare(candidates, report)
            for plugin in extra_plugins:
                self._factories[plugin.name] = _same_instance(plugin)
                plugins.append(plugin)
            self._load(plugins, report)

            self.report = report
            return report

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #
    def list(self) -> list[PackageInfo]:
        with self._lock:
            names = sorted(set(self._sources) | set(self.plugin_manager.loaded_names) | set(self._errors))
            return [self.info(name) for name in names]

    def info(self, name: str) -> PackageInfo:
        with self._lock:
            source = self._sources.get(name)
            plugin = self.plugin_manager.get(name)
            if source is None and plugin is None and name not in self._errors:
                raise NotFoundError(f"Package '{name}' not found")
            status = self._status(name)
            manifest = source.manifest if source is not None else None
            # Both a manifest and a plugin declare version/requires/tools.
            declared = manifest if manifest is not None else plugin
            return PackageInfo(
                name=name,
                status=status,
                version=declared.version if declared else "",
                label=manifest.label if manifest else name,
                description=manifest.description if manifest else "",
                author=manifest.author if manifest else "",
                origin=source.origin if source else ("code" if plugin else ""),
                error=self._errors.get(name) if status == STATUS_FAILED else None,
                requires=tuple(declared.requires) if declared else (),
                requires_tools=tuple(declared.requires_tools) if declared else (),
                provides_tools=tuple(declared.provides_tools) if declared else (),
                extension_points=tuple(declared.extension_points) if declared else (),
                dependents=tuple(self.dependents(name)),
                app_entry=manifest.app_entry if manifest else None,
            )

    def package_status(self, name: str) -> str:
        """active | disabled (known but not loaded, also after a failure) | missing."""

        with self._lock:
            if self.plugin_manager.get(name) is not None:
                return STATUS_ACTIVE
            if name in self._sources or name in self._factories:
                return STATUS_DISABLED
            return STATUS_MISSING

    def dependents(self, name: str) -> list[str]:
        """
        Active packages that need `name`, directly or transitively: they
        list it in `requires`, or use a tool only it provides. Ordered so
        that unloading them in this order never leaves a package without
        what it needs (last loaded first).
        """

        with self._lock:
            loaded = self.plugin_manager.loaded_names
            found: set[str] = set()
            frontier = [name]
            while frontier:
                current = frontier.pop()
                provided = {
                    tool for tool in self.ctx.tool_registry.keys() if self.ctx.tool_registry.owner_of(tool) == current
                }
                for other in loaded:
                    if other == name or other in found:
                        continue
                    plugin = self.plugin_manager.get(other)
                    if plugin is None:
                        continue
                    if current in plugin.requires or provided.intersection(plugin.requires_tools):
                        found.add(other)
                        frontier.append(other)
            return [other for other in reversed(loaded) if other in found]

    # ------------------------------------------------------------------ #
    # Enable / disable
    # ------------------------------------------------------------------ #
    def disable(self, name: str, cascade: bool = False) -> list[str]:
        """
        Unload `name` (and, with cascade, the active packages depending on
        it) and remember it as disabled. Returns the names disabled.
        :raises ConflictError: active packages depend on it and not cascade
        """

        with self._lock:
            self._require_known(name)
            if self.plugin_manager.get(name) is None:
                self.state.set_disabled(name, True)
                return []
            dependents = self.dependents(name)
            if dependents and not cascade:
                raise ConflictError(
                    f"Package '{name}' is needed by {', '.join(dependents)}: disable them first, or use cascade",
                    details={"dependents": dependents},
                )
            disabled = [*dependents, name]
            for package in disabled:
                self.plugin_manager.unload(package)
                self.state.set_disabled(package, True)
            return disabled

    def enable(self, name: str) -> PackageInfo:
        """
        Load `name` again (a fresh plugin instance) and remember it as
        enabled.
        :raises ConflictError: a package it requires is not active
        :raises ValidationError: its manifest checks fail or register() fails
        """

        with self._lock:
            self._require_known(name)
            if self.plugin_manager.get(name) is None:
                source = self._sources.get(name)
                if source is not None:
                    self._check_requires_active(source.manifest)
                    self._check_no_declaration_conflict(source.manifest)
                    problem = self._manifest_problem(source.manifest)
                    if problem is not None:
                        self._errors[name] = str(problem)
                        raise ValidationError(str(problem))
                self._load_one(name, self._factory(name))
            self.state.set_disabled(name, False)
            return self.info(name)

    # ------------------------------------------------------------------ #
    # Install / uninstall
    # ------------------------------------------------------------------ #
    def install(self, stream: BinaryIO, allow_override: bool = False) -> PackageInfo:
        """
        Install a package from a zip and load it at once. A package with
        the name of a bundled one is accepted only in a higher version
        and with allow_override; an installed one is upgraded only to a
        higher version.
        :raises ForbiddenError: installation is disabled on this server
        :raises ValidationError: invalid archive/manifest, missing Python
            libraries, the package fails to load
        :raises ConflictError: name already used, missing `requires`,
            active dependents of the version being replaced
        """

        with self._lock:
            self._require_install_allowed("install")
            staging = self.installed_dir / STAGING_DIR / uuid.uuid4().hex
            try:
                root = extract_package_zip(stream, staging / "package", self.config.limits)
                manifest = load_manifest(root)
                return self._install_from(root, manifest, staging, allow_override)
            finally:
                shutil.rmtree(staging, ignore_errors=True)

    def uninstall(self, name: str) -> None:
        """
        Unload and delete an installed package. Objects it created stay in
        the catalog (their package becomes "missing"). If a bundled
        package of the same name exists, it takes its place.
        :raises ForbiddenError: installation is disabled on this server
        :raises ConflictError: bundled package, or active dependents
        """

        with self._lock:
            self._require_install_allowed("uninstall")
            source = self._sources.get(name)
            if source is None:
                raise NotFoundError(f"Package '{name}' not found")
            if source.origin != ORIGIN_INSTALLED:
                raise ConflictError(f"Package '{name}' ships with SOUP: it can be disabled, not uninstalled")
            dependents = self.dependents(name)
            if dependents:
                raise ConflictError(
                    f"Package '{name}' is needed by {', '.join(dependents)}: disable or uninstall them first",
                    details={"dependents": dependents},
                )
            if self.plugin_manager.get(name) is not None:
                self.plugin_manager.unload(name)
            purge(name)
            shutil.rmtree(source.path, ignore_errors=True)
            self.state.forget(name)
            self._sources.pop(name, None)
            self._factories.pop(name, None)
            self._errors.pop(name, None)
            self._restore_bundled(name)

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _install_from(self, root: Path, manifest: PackageManifest, staging: Path, allow_override: bool) -> PackageInfo:
        name = manifest.name
        existing = self._sources.get(name)
        if existing is not None:
            newer = manifest.parsed_version > existing.manifest.parsed_version
            if existing.origin != ORIGIN_INSTALLED and not (newer and allow_override):
                raise ConflictError(
                    f"Package '{name}' ships with SOUP (version {existing.manifest.version}): only a higher "
                    "version can replace it, and only with explicit confirmation (allow_override)"
                )
            if existing.origin == ORIGIN_INSTALLED and not newer:
                raise ConflictError(
                    f"Package '{name}' is already installed in version {existing.manifest.version}: "
                    "install a higher version to upgrade it"
                )
        problem = self._manifest_problem(manifest)
        if problem is not None:
            raise ValidationError(str(problem))
        self._check_requires_active(manifest)
        self._check_no_declaration_conflict(manifest)
        was_active = self.plugin_manager.get(name) is not None
        if was_active:
            dependents = self.dependents(name)
            if dependents:
                raise ConflictError(
                    f"Package '{name}' is needed by {', '.join(dependents)}: disable them before upgrading it",
                    details={"dependents": dependents},
                )

        target = self.installed_dir / name
        backup = staging / "previous"
        if was_active:
            self.plugin_manager.unload(name)
        purge(name)
        if target.exists():
            os.replace(target, backup)
        os.replace(root, target)

        source = PackageSource(load_manifest(target), target, ORIGIN_INSTALLED)
        try:
            factory = plugin_factory(source)
            self._load_one(name, factory)
        except Exception as exc:
            purge(name)
            shutil.rmtree(target, ignore_errors=True)
            if backup.exists():
                os.replace(backup, target)
            if existing is None:
                self._errors.pop(name, None)
                self._factories.pop(name, None)
            elif was_active:
                self._reload_quietly(existing)
            if isinstance(exc, DomainError):
                raise
            raise ValidationError(f"Package '{name}' could not be loaded: {exc}") from exc

        self._sources[name] = source
        self._factories[name] = factory
        self._errors.pop(name, None)
        self.state.forget(name)
        return self.info(name)

    def _restore_bundled(self, name: str) -> None:
        discovery = discover_packages(self.config.packages_path, self.installed_dir)
        source = discovery.sources.get(name)
        if source is None:
            return
        self._sources[name] = source
        if not self.state.is_disabled(name):
            self._reload_quietly(source)

    def _reload_quietly(self, source: PackageSource) -> None:
        """Best-effort reload of a previous version: failures go to the report and the log."""

        report = PackageReport()
        try:
            self._load(self._prepare([source], report), report)
        except Exception as exc:  # noqa: BLE001 - rollback must not hide the original error
            report.add_failure(source.name, exc)
            self._errors[source.name] = str(exc)
        for failure in report.failed:
            _LOGGER.warning("Package '%s' could not be reloaded: %s", failure.plugin_name, failure.reason)
        self.report.merge(report)

    def _prepare(self, sources: list[PackageSource], report: PackageReport) -> list[SoupPlugin]:
        """
        Manifest-level checks (no code imported yet), ordering with cycle
        isolation, then import. Returns the plugins to load, in order.
        """

        already_loaded = set(self.plugin_manager.loaded_names)
        candidates = {source.name: source for source in sources}

        for name, source in list(candidates.items()):
            problem = self._manifest_problem(source.manifest)
            if problem is not None:
                self._fail(report, name, problem)
                del candidates[name]

        # Global names: the first package (active ones first) keeps a name.
        claims = self._claims()
        for name, source in list(candidates.items()):
            conflict = _declaration_conflict(source.manifest, claims)
            if conflict is not None:
                self._fail(report, name, conflict)
                del candidates[name]
            else:
                claims.update(_claims_of(source.manifest))

        changed = True
        while changed:
            changed = False
            for name, source in list(candidates.items()):
                available = candidates.keys() | already_loaded
                missing = [dep for dep in source.manifest.requires if dep not in available]
                if missing:
                    self._fail(report, name, PluginDependencyError(name, missing))
                    del candidates[name]
                    changed = True

        ordered, blocked = _topological_order(list(candidates.values()))
        for name in blocked:
            self._fail(report, name, PluginCycleError(blocked))

        plugins = []
        failed_imports: set[str] = set()
        for source in ordered:
            missing = [dep for dep in source.manifest.requires if dep in failed_imports]
            if missing:
                self._fail(report, source.name, PluginDependencyError(source.name, missing))
                failed_imports.add(source.name)
                continue
            try:
                factory = plugin_factory(source)
                plugin = factory()
            except Exception as exc:  # noqa: BLE001 - isolate any package failure
                self._fail(report, source.name, exc)
                failed_imports.add(source.name)
                continue
            self._factories[source.name] = factory
            plugins.append(plugin)
        return plugins

    def _load(self, plugins: list[SoupPlugin], report: PackageReport) -> None:
        loaded = self.plugin_manager.load(plugins, ctx=self.ctx)
        for failure in loaded.failed:
            self._errors[failure.plugin_name] = failure.reason
        for name in loaded.loaded:
            self._errors.pop(name, None)
        report.merge(loaded)

    def _load_one(self, name: str, factory: PluginFactory) -> None:
        """:raises ValidationError: the package does not load"""

        report = PackageReport()
        self._load([factory()], report)
        if report.failed:
            raise ValidationError(f"Package '{name}' could not be loaded: {report.failed[0].reason}")

    def _manifest_problem(self, manifest: PackageManifest) -> Optional[Exception]:
        if not is_api_compatible(manifest.api_version, self.config.contracts_api_version):
            return PluginApiVersionError(manifest.name, manifest.api_version, self.config.contracts_api_version)
        problems = python_dependency_problems(manifest, self._version_lookup)
        if problems:
            return PluginPythonDependencyError(manifest.name, problems)
        return None

    def _claims(self) -> dict[tuple[str, str], str]:
        """(kind, global name) -> active package declaring it, for tools and extension points."""

        claims: dict[tuple[str, str], str] = {}
        for tool in self.ctx.tool_registry.keys():
            claims[("tool", tool)] = self.ctx.tool_registry.owner_of(tool) or ""
        for name in self.plugin_manager.loaded_names:
            plugin = self.plugin_manager.get(name)
            if plugin is not None:
                claims.update(_claims_of(plugin))
        return claims

    def _check_no_declaration_conflict(self, manifest: PackageManifest) -> None:
        conflict = _declaration_conflict(manifest, self._claims())
        if conflict is not None:
            raise ConflictError(
                f"Package '{manifest.name}' declares {conflict.kind} '{conflict.key}', already declared by "
                f"active package '{conflict.existing_owner}'",
                details={"conflict": {
                    "kind": conflict.kind,
                    "name": conflict.key,
                    "packages": [conflict.existing_owner, conflict.new_owner],
                }},
            )

    def _check_requires_active(self, manifest: PackageManifest) -> None:
        missing = [dep for dep in manifest.requires if self.plugin_manager.get(dep) is None]
        if missing:
            raise ConflictError(
                f"Package '{manifest.name}' requires packages that are not active: {', '.join(missing)}",
                details={"missing": missing},
            )

    def _factory(self, name: str) -> PluginFactory:
        factory = self._factories.get(name)
        if factory is None:
            factory = plugin_factory(self._sources[name])
            self._factories[name] = factory
        return factory

    def _status(self, name: str) -> str:
        if self.plugin_manager.get(name) is not None:
            return STATUS_ACTIVE
        if name in self._errors and not self.state.is_disabled(name):
            return STATUS_FAILED
        return STATUS_DISABLED

    def _require_known(self, name: str) -> None:
        validate_package_name(name)
        if name not in self._sources and name not in self._factories:
            raise NotFoundError(f"Package '{name}' not found")

    def _require_install_allowed(self, action: str) -> None:
        if not self.config.allow_install:
            raise ForbiddenError(
                f"Package {action} is disabled on this server (set SOUP_ALLOW_PACKAGE_INSTALL=true to allow it)"
            )

    def _fail(self, report: PackageReport, name: str, error: Exception) -> None:
        if self.config.strict:
            raise error
        report.add_failure(name, error)
        self._errors[name] = str(error)


def _claims_of(declared: Any) -> dict[tuple[str, str], str]:
    """The global names a manifest (or a plugin) declares."""

    claims = {("tool", tool): declared.name for tool in declared.provides_tools}
    claims.update({("extension_point", point): declared.name for point in declared.extension_points})
    return claims


def _declaration_conflict(
    manifest: PackageManifest, claims: dict[tuple[str, str], str]
) -> Optional[PluginConflictError]:
    for kind, names in (("tool", manifest.provides_tools), ("extension_point", manifest.extension_points)):
        for name in names:
            owner = claims.get((kind, name))
            if owner is not None and owner != manifest.name:
                return PluginConflictError(kind, name, owner, manifest.name)
    return None


def _same_instance(plugin: SoupPlugin) -> PluginFactory:
    def build() -> SoupPlugin:
        return plugin

    return build


def _topological_order(sources: list[PackageSource]) -> tuple[list[PackageSource], list[str]]:
    """
    Kahn's algorithm on `requires`, stable on the input order. Returns
    the ordered sources and the names left out: those in a cycle and
    those depending on one.
    """

    by_name = {source.name: source for source in sources}
    indegree = {name: 0 for name in by_name}
    dependents: dict[str, list[str]] = {name: [] for name in by_name}
    for source in sources:
        for dep in dict.fromkeys(source.manifest.requires):
            if dep in by_name:
                dependents[dep].append(source.name)
                indegree[source.name] += 1

    position = {name: index for index, name in enumerate(by_name)}
    queue = [name for name, degree in indegree.items() if degree == 0]
    ordered: list[PackageSource] = []
    while queue:
        queue.sort(key=position.__getitem__)
        name = queue.pop(0)
        ordered.append(by_name[name])
        for dependent in dependents[name]:
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                queue.append(dependent)

    done = {source.name for source in ordered}
    return ordered, [name for name in by_name if name not in done]
