"""
------------------------------------------------------------------------
File : test_ocel_cache.py
Description: Tests for the cache of the tables of the ocel package
             (server/cache.py, a copy of csv_table's, and
             store.CachedTables): with a storage that counts its reads,
             the data and "page" actions of "Tabelle OCEL", the export and
             "Scomponi in EKG" read every file of an object once; a new
             import and dispose() invalidate the entry; two objects never
             mix; the LRU keeps at most the given number of objects and a
             log over the size limit is never kept; the limits come from
             SOUP_OCEL_CACHE_OBJECTS and SOUP_OCEL_CACHE_MB (an invalid
             value fails the package); in the engine the plugin instance
             has one cache shared by its contributions, emptied on delete.
Project : soup-packages/ocel
------------------------------------------------------------------------
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from soup.core.contracts import CreatedBy, NotFoundError, ObjectRef, Upload
from tests.api_client import client_for, data_of, import_file
from tests.fakes import FakeDatabase, InMemoryFileStorage, ekg_engine, fake_storage_tool
from tests.packages import bundled_module

store = bundled_module("ocel", "store")
tables = bundled_module("ocel", "tables")
cache_module = bundled_module("ocel", "cache")

FIXTURE = Path(__file__).parent / "fixtures" / "orders.json"
DATA = FIXTURE.read_bytes()
FILES = ("events", "objects", "event_objects", "object_objects", "object_attributes")
PACKAGES = ("tool_memgraph", "tool_storage", "soup_base", "ekg", "ekg_views", "ocel")


class CountingFiles(InMemoryFileStorage):
    """InMemoryFileStorage counting the reads of every path."""

    def __init__(self) -> None:
        super().__init__()
        self.reads: Counter[str] = Counter()

    def read(self, path: str) -> bytes:
        self.reads[path] += 1
        return super().read(path)


class Tools:
    """The ToolAccess of a contribution declaring only "storage"."""

    def __init__(self, files: CountingFiles):
        self._storage = fake_storage_tool(files)

    def get(self, name: str):
        assert name == "storage", name
        return self._storage

    def has(self, name: str) -> bool:
        return name == "storage"


def _obj(object_id: str, meta=None) -> ObjectRef:
    return ObjectRef(object_id, object_id, "ocel_tables", CreatedBy("importer", "ocel.tables", "ocel"), meta=dict(meta or {}))


def _import(cache, tools, object_id: str, content: bytes = DATA) -> ObjectRef:
    meta = tables.OcelTablesImporter(cache).import_(Upload.from_bytes("orders.json", content), _obj(object_id), {}, tools)
    return _obj(object_id, meta)


def _reads(files: CountingFiles, object_id: str) -> dict[str, int]:
    return {
        name: files.reads[f"ocel/{object_id}/{name}.json"] for name in (*FILES, "types")
    }


@pytest.fixture
def files():
    return CountingFiles()


@pytest.fixture
def tools(files):
    return Tools(files)


def test_data_pages_export_read_every_file_of_an_object_once(files, tools):
    cache = store.new_cache()
    obj = _import(cache, tools, "t1")
    visualizer = tables.OcelTablesVisualizer(cache)

    data = visualizer.data(obj, {}, tools)
    pages = [
        visualizer.action(obj, "page", {"table": "events", "offset": 0, "limit": 2}, tools),
        visualizer.action(obj, "page", {"table": "events", "type": "pick item"}, tools),
        visualizer.action(obj, "page", {"table": "objects", "sort": {"column": 2, "direction": "desc"}}, tools),
        visualizer.action(obj, "page", {"table": "object_objects", "search": "ordered"}, tools),
    ]
    exported = json.loads(tables.OcelJsonExporter(cache).export(obj, {}, tools))

    assert _reads(files, "t1") == {name: 1 for name in (*FILES, "types")}
    assert [tab["key"] for tab in data["tables"]] == ["events", "objects", "event_objects", "object_objects"]
    assert [row[0] for row in pages[0]["rows"]] == ["e1", "e2"]
    assert pages[1]["total"] == 2
    assert pages[2]["rows"][0][0] == "o1"
    assert pages[3]["total"] == 1
    assert len(exported["events"]) == 5
    assert cache.keys() == ["t1"]


def test_decompose_into_ekg_reads_the_cached_tables(files, tools, monkeypatch):
    graph = bundled_module("ocel", "graph")
    cache = store.new_cache()
    obj = _import(cache, tools, "t1")
    tables.OcelTablesVisualizer(cache).data(obj, {}, tools)
    built = []
    monkeypatch.setattr(graph, "build", lambda draft, log, extension, tools: built.append(log) or {"dataset": "x"})

    [draft] = graph.DecomposeToEkg(cache).run({"tables": obj}, {}, tools)

    assert draft.meta == {"dataset": "x"}
    assert len(built[0].events) == 5
    assert _reads(files, "t1")["events"] == 1


def test_a_new_import_and_dispose_invalidate_the_entry(files, tools):
    cache = store.new_cache()
    importer = tables.OcelTablesImporter(cache)
    visualizer = tables.OcelTablesVisualizer(cache)
    obj = _import(cache, tools, "t1")
    visualizer.data(obj, {}, tools)
    assert "t1" in cache

    # Imported again under the same id (a new write of the files): read again.
    document = json.loads(DATA)
    document["events"] = document["events"][:1]
    obj = _import(cache, tools, "t1", json.dumps(document).encode("utf-8"))
    assert "t1" not in cache
    assert visualizer.action(obj, "page", {"table": "events"}, tools)["total"] == 1
    assert _reads(files, "t1")["events"] == 2

    importer.dispose(obj, tools)
    assert "t1" not in cache
    with pytest.raises(NotFoundError):
        visualizer.action(obj, "page", {"table": "events"}, tools)


def test_two_objects_never_mix(tools):
    cache = store.new_cache()
    first = _import(cache, tools, "t1")
    document = json.loads(DATA)
    document["events"] = document["events"][:2]
    second = _import(cache, tools, "t2", json.dumps(document).encode("utf-8"))
    visualizer = tables.OcelTablesVisualizer(cache)

    assert visualizer.action(first, "page", {"table": "events"}, tools)["total"] == 5
    assert visualizer.action(second, "page", {"table": "events"}, tools)["total"] == 2
    assert sorted(cache.keys()) == ["t1", "t2"]


def test_the_lru_keeps_the_given_number_of_objects_and_never_a_log_over_the_size_limit(files, tools):
    cache = store.new_cache(max_objects=1)
    visualizer = tables.OcelTablesVisualizer(cache)
    first, second = _import(cache, tools, "t1"), _import(cache, tools, "t2")

    visualizer.data(first, {}, tools)
    visualizer.data(second, {}, tools)
    assert cache.keys() == ["t2"]
    visualizer.data(first, {}, tools)
    assert _reads(files, "t1")["events"] == 2

    loaded = store.load_tables(first, tools)  # without a cache: one more read
    assert _reads(files, "t1")["events"] == 3
    small = store.new_cache(max_bytes=store.estimated_size(loaded) - 1)
    small_visualizer = tables.OcelTablesVisualizer(small)
    small_visualizer.data(first, {}, tools)
    small_visualizer.data(first, {}, tools)
    assert len(small) == 0
    assert _reads(files, "t1")["events"] == 5


def test_the_limits_come_from_the_environment():
    assert cache_module.limits_from_env({}, "SOUP_OCEL") == (8, 200 * 1024 * 1024)
    assert cache_module.limits_from_env({"SOUP_OCEL_CACHE_OBJECTS": "3", "SOUP_OCEL_CACHE_MB": "5"}, "SOUP_OCEL") == (
        3, 5 * 1024 * 1024,
    )
    with pytest.raises(ValueError, match="SOUP_OCEL_CACHE_MB"):
        cache_module.limits_from_env({"SOUP_OCEL_CACHE_MB": "0"}, "SOUP_OCEL")


def test_in_the_engine_the_contributions_share_the_plugin_cache_emptied_on_delete(tmp_path, monkeypatch):
    monkeypatch.setenv("SOUP_OCEL_CACHE_OBJECTS", "3")
    engine = ekg_engine(tmp_path, monkeypatch, packages=PACKAGES, db=FakeDatabase())
    assert engine.report.failed == [], engine.report.failed
    client = client_for(engine)
    ctx = engine.ctx
    cache = ctx.importers.get("ocel.tables").cache
    assert all(
        item.cache is cache
        for item in (ctx.visualizers.get("ocel.tables"), ctx.operations.get("ocel.to_ekg"), ctx.exporters.get("ocel.json"))
    )
    assert cache.max_objects == 3

    response = import_file(client, "ocel.tables", name="orders", filename="orders.json", content=DATA)
    object_id = data_of(response)["id"]
    client.post(f"/api/v3/objects/{object_id}/visualizers/ocel.tables/actions/page", json={"table": "events"})
    assert object_id in cache
    assert client.delete(f"/api/v3/objects/{object_id}").status_code == 200
    assert object_id not in cache


def test_an_invalid_limit_fails_the_package_with_a_message(tmp_path, monkeypatch):
    monkeypatch.setenv("SOUP_OCEL_CACHE_MB", "lots")
    engine = ekg_engine(tmp_path, monkeypatch, packages=PACKAGES, db=FakeDatabase())

    failures = {failure.plugin_name: str(failure.error) for failure in engine.report.failed}
    assert "SOUP_OCEL_CACHE_MB" in failures["ocel"]
