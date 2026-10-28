"""
------------------------------------------------------------------------
File : preparation.py
Description: PackagePreparer - from the packages found on disk to the
             plugins the PluginManager loads, in order. Each step drops
             (and reports through `fail`) the packages that cannot load,
             before any of their code is imported:
             1. manifest problems (api_version, python_dependencies);
             2. global names (tools, extension points) already declared:
                the first package, active ones first, keeps a name;
             3. `requires` neither active nor among the candidates
                (repeated until nothing changes);
             4. ordering on `requires`, isolating the cycles;
             5. import under soup_pkg_<name>: a package requiring one
                whose import failed is dropped too.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from collections.abc import Callable

from soup.core.contracts import PluginCycleError, PluginDependencyError, SoupPlugin
from soup.core.ordering import topological_order
from soup.core.packages.checks import PackageChecks, claims_of, declaration_conflict
from soup.core.packages.discovery import PackageSource
from soup.core.packages.loader import PluginFactory, plugin_factory
from soup.core.plugin_manager import PackageReport, PluginManager

Fail = Callable[[PackageReport, str, Exception], None]
Candidates = dict[str, PackageSource]


class PackagePreparer:
    def __init__(self, plugin_manager: PluginManager, checks: PackageChecks, fail: Fail):
        self._plugins = plugin_manager
        self._checks = checks
        self._fail = fail

    def prepare(
        self, sources: list[PackageSource], report: PackageReport
    ) -> tuple[list[SoupPlugin], dict[str, PluginFactory]]:
        """The plugins to load, in order, and the factory of each."""

        candidates = {source.name: source for source in sources}
        self._drop_manifest_problems(candidates, report)
        self._drop_declaration_conflicts(candidates, report)
        self._drop_missing_requires(candidates, report)
        return self._import(self._ordered(candidates, report), report)

    def _drop_manifest_problems(self, candidates: Candidates, report: PackageReport) -> None:
        for name, source in list(candidates.items()):
            problem = self._checks.manifest_problem(source.manifest)
            if problem is not None:
                self._fail(report, name, problem)
                del candidates[name]

    def _drop_declaration_conflicts(self, candidates: Candidates, report: PackageReport) -> None:
        claims = self._checks.claims()
        for name, source in list(candidates.items()):
            conflict = declaration_conflict(source.manifest, claims)
            if conflict is not None:
                self._fail(report, name, conflict)
                del candidates[name]
            else:
                claims.update(claims_of(source.manifest))

    def _drop_missing_requires(self, candidates: Candidates, report: PackageReport) -> None:
        already_loaded = set(self._plugins.loaded_names)
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

    def _ordered(self, candidates: Candidates, report: PackageReport) -> list[PackageSource]:
        order, blocked = topological_order(
            list(candidates), {name: source.manifest.requires for name, source in candidates.items()}
        )
        for name in blocked:
            self._fail(report, name, PluginCycleError(blocked))
        return [candidates[name] for name in order]

    def _import(
        self, ordered: list[PackageSource], report: PackageReport
    ) -> tuple[list[SoupPlugin], dict[str, PluginFactory]]:
        plugins: list[SoupPlugin] = []
        factories: dict[str, PluginFactory] = {}
        failed: set[str] = set()
        for source in ordered:
            missing = [dep for dep in source.manifest.requires if dep in failed]
            if missing:
                self._fail(report, source.name, PluginDependencyError(source.name, missing))
                failed.add(source.name)
                continue
            try:
                factory = plugin_factory(source)
                plugin = factory()
            except Exception as exc:  # noqa: BLE001 - isolate any package failure
                self._fail(report, source.name, exc)
                failed.add(source.name)
                continue
            factories[source.name] = factory
            plugins.append(plugin)
        return plugins, factories
