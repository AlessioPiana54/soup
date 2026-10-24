"""
------------------------------------------------------------------------
File : engine.py
Description: build_engine() is the single composition root: it wires the
             GraphDatabase/FileStorage adapters (or uses the ones injected
             for testing), discovers/loads the packages (PackageManager,
             from Settings.packages_path) and assembles the core's own services: the legacy
             import path (DatasetRepository, EkgService, EventLogHandler,
             ImportService, behind /api/v2/graph) and the mediator
             (ImportRouter, OperationRouter, VisualizerRouter,
             ExportRouter, WorkspaceService), which reaches the
             catalog/preferences tools provided by packages. If those
             tools are missing the engine still starts: the report lists
             the problem and the services answer 503.
             Nothing outside this module decides which concrete adapter,
             plugin, or service wiring to use.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

from soup.core.contracts import CONTRACTS_API_VERSION, EVENT_LOG, FileStorage, GraphDatabase
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
    db: GraphDatabase
    storage: FileStorage
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
        self.plugin_manager.shutdown()

        # GraphDatabase does not declare close() (not every adapter needs
        # one - FakeDatabase doesn't), so call it only if the concrete
        # instance actually has it (MemgraphDatabase does).
        close = getattr(self.db, "close", None)
        if callable(close):
            close()


def _build_default_database(settings: Settings) -> GraphDatabase:
    from soup.infrastructure.memgraph import MemgraphDatabase

    uri = f"bolt://{settings.memgraph_host}:{settings.memgraph_port}"
    return MemgraphDatabase(uri=uri, auth=("", ""))


def _build_default_storage(settings: Settings) -> FileStorage:
    if settings.storage_kind == "local":
        from soup.infrastructure.local_storage import LocalFileStorage

        return LocalFileStorage(root=settings.local_storage_root)

    from soup.infrastructure.docker_storage import DockerVolumeStorage

    return DockerVolumeStorage(container_name=settings.container_name, root=settings.local_storage_root)


def build_engine(
    settings: Settings,
    db: Optional[GraphDatabase] = None,
    storage: Optional[FileStorage] = None,
    extra_plugins: Iterable[Any] = (),
) -> Engine:
    """
    Single composition root. `db`/`storage` are normally omitted and built
    from `settings`; tests inject fakes (tests.fakes.FakeDatabase,
    tests.fakes.InMemoryFileStorage) instead. `extra_plugins` are loaded
    together with the packages found on disk (SoupPlugin
    instances/classes or specs); tests use it for packages defined in
    the test itself.
    """

    resolved_db = db if db is not None else _build_default_database(settings)
    resolved_storage = storage if storage is not None else _build_default_storage(settings)

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

    repository = DatasetRepository(resolved_storage, root=settings.local_storage_root)
    ekg_service = EkgService(resolved_db, plugin_build_steps=ctx.build_steps)

    # Core-registered, not plugin-attributed: the core ships the
    # event-log handler itself, the way a plugin ships a build step.
    event_log_handler = EventLogHandler(repository, ekg_service)
    ctx.input_handlers.register(event_log_handler, owner=CORE_OWNER, key=EVENT_LOG)

    import_service = ImportService(ctx.input_readers, ctx.input_handlers)

    return Engine(
        settings=settings,
        db=resolved_db,
        storage=resolved_storage,
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
