"""
------------------------------------------------------------------------
File : test_text_and_csv_table_cache.py
Description: Tests for the cache of the parsed files of the text and
             csv_table packages (server/cache.py of each): with a storage
             that counts its reads, several "page" actions (and the other
             reads of a table) on the same object read the file once, and
             so do the "lines"/"search" actions of a text; dispose()
             empties the entry and a new write of the file invalidates it;
             the LRU drops the least recently used object, by number and
             by estimated size; a file over the size limit is never kept;
             two objects never mix; an invalidation during a load wins;
             the limits come from the environment; and in the engine each
             plugin instance has its own cache, shared by its
             contributions, emptied on delete and replaced by
             disable/enable.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import threading
from collections import Counter

import pytest

from soup.core.contracts import CreatedBy, ObjectRef, Upload
from soup.core.engine import build_engine
from soup.core.settings import Settings
from tests.api_client import client_for, data_of, import_file
from tests.fakes import InMemoryFileStorage, fake_storage_tool
from tests.packages import BUNDLED_PACKAGES_DIR, bundled_api

csv_api = bundled_api("csv_table")
text_api = bundled_api("text")

CSV = b"id,activity\n1,Create\n2,Ship\n3,Pay\n"
OTHER_CSV = b"id,activity\n9,Archive\n"
TEXT = b"alpha\nbeta\ngamma\n"


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


def _obj(object_id: str, kind: str, meta=None) -> ObjectRef:
    return ObjectRef(object_id, object_id, kind, CreatedBy("importer", f"x.{kind}", "x"), meta=dict(meta or {}))


@pytest.fixture
def files():
    return CountingFiles()


@pytest.fixture
def tools(files):
    return Tools(files)


def _table(tools, cache, object_id: str, content: bytes = CSV) -> ObjectRef:
    importer = csv_api.CsvTableImporter(cache)
    obj = _obj(object_id, "table")
    meta = importer.import_(Upload.from_bytes(f"{object_id}.csv", content), obj, {}, tools)
    return _obj(object_id, "table", meta)


def _page(cache, obj, tools, **params):
    return csv_api.CsvTableVisualizer(cache).action(obj, "page", {"offset": 0, "limit": 10, **params}, tools)


# ---------------------------------------------------------------------- #
# csv_table
# ---------------------------------------------------------------------- #
def test_many_page_actions_read_the_file_once(files, tools):
    cache = csv_api.new_cache()
    table = _table(tools, cache, "t1")
    visualizer = csv_api.CsvTableVisualizer(cache)

    pages = [
        visualizer.action(table, "page", {"offset": 0, "limit": 2}, tools),
        visualizer.action(table, "page", {"offset": 2, "limit": 2}, tools),
        visualizer.action(table, "page", {"sort": {"column": 1, "direction": "desc"}}, tools),
        visualizer.action(table, "page", {"filter": [{"column": 1, "value": "sh"}]}, tools),
    ]
    visualizer.data(table, {}, tools)
    csv_api.CsvProfileVisualizer(cache).action(table, "distribution", {"column": 1}, tools)

    assert files.reads["csv_table/t1.csv"] == 1
    assert pages[0] == {"rows": [("1", "Create"), ("2", "Ship")], "total": 3}
    assert [row[1] for row in pages[2]["rows"]] == ["Ship", "Pay", "Create"]
    assert pages[3]["total"] == 1
    assert cache.keys() == ["t1"]


def test_dispose_empties_the_cache_and_removes_the_file(files, tools):
    cache = csv_api.new_cache()
    importer = csv_api.CsvTableImporter(cache)
    table = _table(tools, cache, "t1")
    _page(cache, table, tools)
    assert "t1" in cache

    importer.dispose(table, tools)

    assert len(cache) == 0 and cache.total_bytes == 0
    assert "csv_table/t1.csv" not in files.paths


def test_writing_the_file_again_invalidates_the_entry(files, tools):
    cache = csv_api.new_cache()
    table = _table(tools, cache, "t1")
    assert _page(cache, table, tools)["total"] == 3

    table = _table(tools, cache, "t1", OTHER_CSV)

    assert "t1" not in cache
    assert _page(cache, table, tools)["rows"] == [("9", "Archive")]
    assert files.reads["csv_table/t1.csv"] == 2


def test_the_lru_drops_the_least_recently_used_object(files, tools):
    cache = csv_api.new_cache(max_objects=2)
    first, second, third = (_table(tools, cache, name) for name in ("a", "b", "c"))

    _page(cache, first, tools)
    _page(cache, second, tools)
    _page(cache, first, tools)  # "a" is now the most recently used
    _page(cache, third, tools)

    assert cache.keys() == ["a", "c"]
    _page(cache, second, tools)
    assert files.reads == Counter({"csv_table/a.csv": 1, "csv_table/b.csv": 2, "csv_table/c.csv": 1})
    assert cache.keys() == ["c", "b"]


def test_the_size_limit_drops_old_objects_and_never_keeps_a_larger_file(files, tools):
    one_table = csv_api.new_cache()
    small = _table(tools, one_table, "small")
    _page(one_table, small, tools)
    size = one_table.total_bytes
    assert size > 0

    cache = csv_api.new_cache(max_objects=8, max_bytes=size * 2)
    first, second, third = (_table(tools, cache, name) for name in ("a", "b", "c"))
    for table in (first, second, third):
        _page(cache, table, tools)
    assert cache.keys() == ["b", "c"]
    assert cache.total_bytes <= size * 2

    tiny = csv_api.new_cache(max_bytes=size - 1)
    big = _table(tools, tiny, "big")
    _page(tiny, big, tools)
    _page(tiny, big, tools)
    # Too large for the cache: read every time, as without it.
    assert len(tiny) == 0
    assert files.reads["csv_table/big.csv"] == 2


def test_two_objects_never_mix(files, tools):
    cache = csv_api.new_cache()
    first = _table(tools, cache, "a")
    second = _table(tools, cache, "b", OTHER_CSV)

    assert _page(cache, first, tools)["total"] == 3
    assert _page(cache, second, tools)["rows"] == [("9", "Archive")]
    assert _page(cache, first, tools)["rows"][0] == ("1", "Create")
    exported = csv_api.CsvExporter(cache).export(second, {"separator": "comma", "header": True}, tools)
    assert exported == b"id,activity\n9,Archive\n"


def test_cached_tables_are_immutable(tools):
    cache = csv_api.new_cache()
    table = _table(tools, cache, "t1")
    rows = _page(cache, table, tools)["rows"]
    with pytest.raises(TypeError):
        rows[0][0] = "changed"  # type: ignore[index]


# ---------------------------------------------------------------------- #
# text
# ---------------------------------------------------------------------- #
def _text(tools, cache, object_id: str, content: bytes = TEXT) -> ObjectRef:
    obj = _obj(object_id, "text")
    meta = text_api.TextImporter(cache).import_(Upload.from_bytes(f"{object_id}.txt", content), obj, {}, tools)
    return _obj(object_id, "text", meta)


def test_lines_and_search_read_the_text_once_and_dispose_empties_the_cache(files, tools):
    cache = text_api.new_cache()
    notes = _text(tools, cache, "n1")
    other = _text(tools, cache, "n2", b"other\n")
    visualizer = text_api.TextVisualizer(cache)

    assert visualizer.data(notes, {}, tools)["lines"] == ["alpha", "beta", "gamma"]
    assert visualizer.action(notes, "lines", {"from": 1, "count": 1}, tools)["lines"] == ["beta"]
    assert visualizer.action(notes, "search", {"query": "a"}, tools)["total"] == 3
    assert visualizer.action(other, "lines", {}, tools)["lines"] == ["other"]
    assert files.reads == Counter({"text/n1": 1, "text/n2": 1})

    text_api.TextImporter(cache).dispose(notes, tools)
    assert cache.keys() == ["n2"]
    # The export reads the stored bytes, not the cache.
    assert text_api.OriginalFileExporter().export(other, {}, tools) == b"other\n"


def test_text_lru_and_size_limit(files, tools):
    cache = text_api.new_cache(max_objects=1)
    first, second = _text(tools, cache, "a"), _text(tools, cache, "b")
    visualizer = text_api.TextVisualizer(cache)
    visualizer.action(first, "lines", {}, tools)
    visualizer.action(second, "lines", {}, tools)
    assert cache.keys() == ["b"]

    tiny = text_api.new_cache(max_bytes=10)
    big = _text(tools, tiny, "big")
    text_api.TextVisualizer(tiny).action(big, "lines", {}, tools)
    assert len(tiny) == 0


# ---------------------------------------------------------------------- #
# ParsedCache and limits
# ---------------------------------------------------------------------- #
def test_an_invalidation_during_a_load_wins():
    cache = csv_api.ParsedCache(len)
    loading, release = threading.Event(), threading.Event()
    result = {}

    def slow_load():
        loading.set()
        release.wait(5)
        return "stale"

    worker = threading.Thread(target=lambda: result.setdefault("value", cache.get("k", slow_load)))
    worker.start()
    assert loading.wait(5)
    cache.invalidate("k")
    release.set()
    worker.join(5)

    assert result["value"] == "stale"
    assert "k" not in cache
    assert cache.get("k", lambda: "fresh") == "fresh"


def test_concurrent_gets_keep_one_consistent_entry():
    cache = csv_api.ParsedCache(len, max_objects=4)
    errors = []

    def work(index: int) -> None:
        try:
            for round_ in range(200):
                key = f"k{(index + round_) % 6}"
                assert cache.get(key, lambda key=key: key * 3) == key * 3
        except Exception as exc:  # noqa: BLE001 - reported below
            errors.append(exc)

    threads = [threading.Thread(target=work, args=(index,)) for index in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(10)

    assert errors == []
    assert len(cache) <= 4
    assert cache.total_bytes == sum(len(key) * 3 for key in cache.keys())


@pytest.mark.parametrize("api", [csv_api, text_api], ids=["csv_table", "text"])
def test_limits_from_the_environment(api):
    assert api.limits_from_env({}, "SOUP_X") == (8, 200 * 1024 * 1024)
    assert (api.DEFAULT_MAX_OBJECTS, api.DEFAULT_MAX_BYTES) == (8, 200 * 1024 * 1024)
    assert api.limits_from_env({"SOUP_X_CACHE_OBJECTS": "3", "SOUP_X_CACHE_MB": "16"}, "SOUP_X") == (3, 16 * 1024 * 1024)
    for bad in ("0", "-2", "many"):
        with pytest.raises(ValueError, match="SOUP_X_CACHE_MB"):
            api.limits_from_env({"SOUP_X_CACHE_MB": bad}, "SOUP_X")
    with pytest.raises(ValueError):
        api.ParsedCache(len, max_objects=0)


# ---------------------------------------------------------------------- #
# In the engine: one cache per plugin instance
# ---------------------------------------------------------------------- #
def test_each_plugin_instance_owns_the_cache_of_its_contributions(tmp_path, monkeypatch):
    monkeypatch.setenv("SOUP_STORAGE_KIND", "local")
    monkeypatch.setenv("SOUP_LOCAL_STORAGE_ROOT", str(tmp_path / "volume"))
    monkeypatch.setenv("SOUP_CSV_TABLE_CACHE_OBJECTS", "3")
    installed = tmp_path / "installed"
    engine = build_engine(Settings(
        packages=("soup_base", "tool_storage", "text", "csv_table"),
        packages_path=(str(BUNDLED_PACKAGES_DIR), str(installed)),
        installed_packages_dir=str(installed),
    ))
    assert engine.report.failed == []
    client = client_for(engine)

    def caches():
        ctx = engine.ctx
        return (
            ctx.importers.get("csv_table.csv").cache,
            ctx.visualizers.get("csv_table.table").cache,
            ctx.visualizers.get("csv_table.profile").cache,
            ctx.operations.get("csv_table.distribution").cache,
            ctx.exporters.get("csv_table.csv").cache,
        )

    first = caches()
    assert all(cache is first[0] for cache in first)
    assert first[0].max_objects == 3
    assert engine.ctx.visualizers.get("text.text").cache is engine.ctx.importers.get("text.text").cache
    assert engine.ctx.visualizers.get("text.text").cache is not first[0]

    response = import_file(client, "csv_table.csv", name="orders", filename="orders.csv", content=CSV)
    object_id = data_of(response)["id"]
    assert client.post(f"/api/v3/objects/{object_id}/visualizers/csv_table.table/actions/page", json={}).status_code == 200
    assert object_id in first[0]

    # Deleting the object goes through dispose(), which empties its entry.
    assert client.delete(f"/api/v3/objects/{object_id}").status_code == 200
    assert object_id not in first[0]

    # disable/enable: a new plugin instance with a new, empty cache.
    engine.package_manager.disable("csv_table")
    engine.package_manager.enable("csv_table")
    second = caches()
    assert second[0] is not first[0]
    assert len(second[0]) == 0
