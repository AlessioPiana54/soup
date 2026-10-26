"""
------------------------------------------------------------------------
File : fakes.py
Description: In-memory fakes used by every test instead of Memgraph and
             Docker: FakeDatabase (GraphDatabase) and InMemoryFileStorage
             (a FileStorage backend), the catalog and preferences tools
             (InMemoryCatalog, InMemoryPreferences, CoreToolsPackage),
             and the "memgraph" and "storage" tools of the tool_memgraph
             and tool_storage packages built on them
             (fake_memgraph_tool, fake_storage_tool, LegacyToolsPackage,
             fake_tool_engine).
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

from soup.core.contracts import (
    Catalog,
    ConflictError,
    FileStorage,
    GraphDatabase,
    NotFoundError,
    ObjectRef,
    PluginContext,
    Preferences,
    Query,
    SoupPlugin,
)


class InMemoryFileStorage(FileStorage):
    """
    FileStorage fake backed by a plain dict - no filesystem/Docker I/O.
    Behaves like the real backends: "/" separates folders, list(prefix)
    returns the names directly under prefix and delete(path) removes a
    file or a whole folder.
    """

    def __init__(self) -> None:
        self._files: dict[str, bytes] = {}

    def read(self, path: str) -> bytes:
        if path not in self._files:
            raise FileNotFoundError(path)
        return self._files[path]

    def write(self, path: str, data: bytes) -> None:
        self._files[path] = bytes(data)

    def exists(self, path: str) -> bool:
        return path in self._files

    def delete(self, path: str) -> None:
        folder = path.rstrip("/") + "/"
        for key in [key for key in self._files if key == path or key.startswith(folder)]:
            del self._files[key]

    def list(self, prefix: str = "") -> list[str]:
        folder = prefix.strip("/")
        folder = folder + "/" if folder else ""
        return sorted({path[len(folder):].split("/")[0] for path in self._files if path.startswith(folder)})

    @property
    def paths(self) -> list[str]:
        """Every file stored, by full path (white-box checks)."""

        return sorted(self._files)


class FakeDatabase(GraphDatabase):
    """
    GraphDatabase fake that records every Query it receives (text and
    params, in order) and returns a configurable canned response per
    query text, falling back to a default response.
    """

    def __init__(self) -> None:
        self.received_queries: list[Query] = []
        self._responses: dict[str, list[dict[str, Any]]] = {}
        self._default_response: list[dict[str, Any]] = []

    def set_response(self, query_text: str, rows: list[dict[str, Any]]) -> None:
        self._responses[query_text] = rows

    def set_default_response(self, rows: list[dict[str, Any]]) -> None:
        self._default_response = rows

    def run(self, query: Query) -> list[dict[str, Any]]:
        self.received_queries.append(query)
        return self._responses.get(query.text, self._default_response)


class InMemoryCatalog(Catalog):
    """Catalog fake backed by dicts, following the port's error contract."""

    def __init__(self) -> None:
        self.objects: dict[str, ObjectRef] = {}
        self.thumbnails: dict[str, Optional[str]] = {}

    def health(self) -> dict[str, Any]:
        return {"ok": True}

    def add(self, obj: ObjectRef) -> None:
        if obj.id in self.objects:
            raise ConflictError(f"Object '{obj.id}' already exists")
        self.objects[obj.id] = obj

    def get(self, object_id: str) -> Optional[ObjectRef]:
        return self.objects.get(object_id)

    def list(self) -> list[ObjectRef]:
        return list(self.objects.values())

    def children(self, object_id: str) -> list[ObjectRef]:
        return [obj for obj in self.objects.values() if object_id in obj.parents]

    def update(self, obj: ObjectRef) -> None:
        self._require(obj.id)
        self.objects[obj.id] = obj

    def remove(self, object_id: str) -> None:
        self._require(object_id)
        del self.objects[object_id]
        self.thumbnails.pop(object_id, None)

    def get_thumbnail(self, object_id: str) -> Optional[str]:
        self._require(object_id)
        return self.thumbnails.get(object_id)

    def set_thumbnail(self, object_id: str, svg: Optional[str]) -> None:
        self._require(object_id)
        self.thumbnails[object_id] = svg

    def _require(self, object_id: str) -> None:
        if object_id not in self.objects:
            raise NotFoundError(f"Object '{object_id}' not found")


class InMemoryPreferences(Preferences):
    def __init__(self) -> None:
        self.values: dict[str, Any] = {}

    def health(self) -> dict[str, Any]:
        return {"ok": True}

    def get(self, key: str) -> Any:
        return self.values.get(key)

    def set(self, key: str, value: Any) -> None:
        self.values[key] = value


class CoreToolsPackage(SoupPlugin):
    """Test package providing the catalog and preferences tools in memory."""

    name = "test_core_tools"
    version = "1.0.0"
    provides_tools = ("catalog", "preferences")

    def __init__(self) -> None:
        self.catalog = InMemoryCatalog()
        self.preferences = InMemoryPreferences()

    def register(self, ctx: PluginContext) -> None:
        ctx.add_tool(self.catalog)
        ctx.add_tool(self.preferences)


def fake_memgraph_tool(db: Optional[GraphDatabase] = None):
    """The tool_memgraph package's MemgraphTool on a FakeDatabase."""

    from tests.packages import bundled_api

    return bundled_api("tool_memgraph").MemgraphTool(db if db is not None else FakeDatabase())


def fake_storage_tool(files: Optional[FileStorage] = None, root: str = "/soup"):
    """The tool_storage package's StorageTool on an InMemoryFileStorage."""

    from tests.packages import bundled_api

    return bundled_api("tool_storage").StorageTool(files if files is not None else InMemoryFileStorage(), root=root)


class LegacyToolsPackage(SoupPlugin):
    """
    Test package providing the "memgraph" and "storage" tools (the real
    tool classes) on a FakeDatabase and an InMemoryFileStorage. `db` and
    `files` stay reachable for assertions.
    """

    name = "test_legacy_tools"
    version = "1.0.0"
    provides_tools = ("memgraph", "storage")

    def __init__(self, db: Optional[GraphDatabase] = None, files: Optional[FileStorage] = None) -> None:
        self.db = db if db is not None else FakeDatabase()
        self.files = files if files is not None else InMemoryFileStorage()
        self.memgraph = fake_memgraph_tool(self.db)
        self.storage = fake_storage_tool(self.files)

    def register(self, ctx: PluginContext) -> None:
        ctx.add_tool(self.memgraph)
        ctx.add_tool(self.storage)


def fake_tool_engine(
    settings,
    db: Optional[GraphDatabase] = None,
    files: Optional[FileStorage] = None,
    extra_plugins: Iterable[Any] = (),
):
    """
    build_engine(settings) with the in-memory "memgraph" and "storage"
    tools (LegacyToolsPackage) in place of tool_memgraph and tool_storage,
    which `settings` must therefore not activate.
    """

    from soup.core.engine import build_engine

    return build_engine(settings, extra_plugins=[LegacyToolsPackage(db, files), *extra_plugins])
