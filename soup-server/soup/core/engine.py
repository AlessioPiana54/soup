"""
------------------------------------------------------------------------
File : engine.py
Description: build_engine() is the single composition root: it
             discovers/loads the packages (PackageManager, from
             Settings.packages_path, plus the ones tests pass in code)
             and assembles the core's own services: the legacy import
             path (DatasetRepository, EkgService, EventLogHandler,
             ImportService, behind /api/v2/graph), which reaches the
             "memgraph" and "storage" tools, and the mediator
             (ImportRouter, OperationRouter, VisualizerRouter,
             ExportRouter, WorkspaceService), which reaches the
             catalog/preferences tools. Every tool is provided by a
             package (tool_memgraph, tool_storage): the core builds no
             database or storage adapter. If a tool is missing the
             engine still starts: the report lists the problem and the
             services that need it answer 503.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from soup.core.contracts import CONTRACTS_API_VERSION, EVENT_LOG
from soup.core.dataset_repository import DatasetRepository
from soup.core.event_bus import EventBus
from soup.core.plugin_context import DefaultPluginContext
from soup.core.packages import PackageManager, PackageManagerConfig
from soup.core.plugin_manager import PackageReport, PluginManager
from soup.core.services.core_tools import CoreTools, missing_core_tools
from soup.core.services.ekg_service import EkgService
from soup.core.services.event_log_handler import EventLogHandler
from soup.core.services.export_router import ExportRouter
from soup.core.services.import_router import ImportRouter
from soup.core.services.import_service import ImportService
from soup.core.services.legacy_tools import ToolGraph, ToolStorage
from soup.core.services.operation_router import OperationRouter
from soup.core.services.orphaned_data import ORPHANED_DATA_FILE, OrphanedDataLog
from soup.core.services.visualizer_router import VisualizerRouter
from soup.core.services.workspace_service import WorkspaceService
from soup.core.settings import Settings

# The core owns kind=EVENT_LOG end to end (EventLogHandler); it is
# registered directly into ctx.input_handlers below, attributed to this
# synthetic "core" owner rather than to any plugin.
CORE_OWNER = "core"


@dataclass
class Engine:
    settings: Settings
    ctx: DefaultPluginContext
    plugin_manager: PluginManager
    package_manager: PackageManager
    report: PackageReport
    repository: DatasetRepository
    ekg_service: EkgService
    import_service: ImportService
    event_bus: EventBus
    core_tools: CoreTools
    import_router: ImportRouter
    operation_router: OperationRouter
    visualizer_router: VisualizerRouter
    export_router: ExportRouter
    workspace_service: WorkspaceService

    def shutdown(self) -> None:
        # The packages release their own resources in on_shutdown (e.g.
        # tool_memgraph closes the Memgraph driver).
        self.plugin_manager.shutdown()


def build_engine(settings: Settings, extra_plugins: Iterable[Any] = ()) -> Engine:
    """
    Single composition root. `extra_plugins` are loaded together with the
    packages found on disk (SoupPlugin instances/classes or specs); tests
    use it for packages defined in the test itself, e.g. the in-memory
    tools of tests.fakes.FakeToolsPackage.
    """

    manager = PluginManager(contracts_api_version=CONTRACTS_API_VERSION, strict=settings.strict)
    event_bus = EventBus()
    ctx = DefaultPluginContext(event_bus)

    package_manager = PackageManager(
        manager,
        ctx,
        PackageManagerConfig(
            packages_path=settings.packages_path,
            installed_dir=settings.installed_packages_dir,
            enabled_override=settings.packages,
            allow_install=settings.allow_package_install,
            strict=settings.strict,
        ),
    )
    report = package_manager.load_all(manager.discover(extra_plugins))
    for problem in missing_core_tools(ctx.tool_registry):
        report.add_warning(problem)

    core_tools = CoreTools(ctx.tool_registry)

    repository = DatasetRepository(ToolStorage(core_tools))
    ekg_service = EkgService(ToolGraph(core_tools), plugin_build_steps=ctx.build_steps)

    # Core-registered, not plugin-attributed: the core ships the
    # event-log handler itself, the way a plugin ships a build step.
    event_log_handler = EventLogHandler(repository, ekg_service)
    ctx.input_handlers.register(event_log_handler, owner=CORE_OWNER, key=EVENT_LOG)

    import_service = ImportService(ctx.input_readers, ctx.input_handlers)

    return Engine(
        settings=settings,
        ctx=ctx,
        plugin_manager=manager,
        package_manager=package_manager,
        report=report,
        repository=repository,
        ekg_service=ekg_service,
        import_service=import_service,
        event_bus=event_bus,
        core_tools=core_tools,
        import_router=ImportRouter(ctx.importers, core_tools, event_bus),
        operation_router=OperationRouter(ctx.operations, core_tools, event_bus),
        visualizer_router=VisualizerRouter(ctx.visualizers, core_tools),
        export_router=ExportRouter(ctx.exporters, core_tools),
        workspace_service=WorkspaceService(
            ctx.importers,
            ctx.operations,
            core_tools,
            event_bus,
            package_status=package_manager.package_status,
            orphaned_data=OrphanedDataLog(Path(settings.installed_packages_dir) / ORPHANED_DATA_FILE),
        ),
    )
