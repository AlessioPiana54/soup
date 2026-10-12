"""
------------------------------------------------------------------------
File : engine.py
Description: build_engine() is the single composition root: it wires the
             GraphDatabase/FileStorage adapters (or uses the ones injected
             for testing) and discovers/loads the plugins declared in
             Settings. Nothing outside this module decides which concrete
             adapter or plugin implementation to use.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from soup.core.contracts import CONTRACTS_API_VERSION, FileStorage, GraphDatabase
from soup.core.plugin_context import DefaultPluginContext
from soup.core.plugin_manager import PluginManager, PluginReport
from soup.core.settings import Settings


@dataclass
class Engine:
    settings: Settings
    db: GraphDatabase
    storage: FileStorage
    ctx: DefaultPluginContext
    plugin_manager: PluginManager
    report: PluginReport

    def shutdown(self) -> None:
        self.plugin_manager.shutdown()


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


def build_engine(settings: Settings, db: Optional[GraphDatabase] = None, storage: Optional[FileStorage] = None) -> Engine:
    """
    Single composition root. `db`/`storage` are normally omitted and built
    from `settings`; tests inject fakes (tests.fakes.FakeDatabase,
    tests.fakes.InMemoryFileStorage) instead.
    """

    resolved_db = db if db is not None else _build_default_database(settings)
    resolved_storage = storage if storage is not None else _build_default_storage(settings)

    manager = PluginManager(contracts_api_version=CONTRACTS_API_VERSION, strict=settings.strict)
    ctx = DefaultPluginContext()

    plugins = manager.discover(list(settings.plugins))
    report = manager.load(plugins, ctx=ctx)

    return Engine(
        settings=settings,
        db=resolved_db,
        storage=resolved_storage,
        ctx=ctx,
        plugin_manager=manager,
        report=report,
    )
