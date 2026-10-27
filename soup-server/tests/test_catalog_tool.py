"""
------------------------------------------------------------------------
File : test_catalog_tool.py
Description: The Catalog port's contract, run against the tool_storage
             package's FileCatalog (on the in-memory and the local
             backend) and against the in-memory InMemoryCatalog the other
             tests use, so the two cannot drift apart: add, get, list,
             children, update, remove, thumbnails; plus FileCatalog's
             layout (<root>/_catalog/objects/<id>.json,
             <root>/_catalog/thumbnails/<id>.svg) and persistence.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import json
import uuid

import pytest

from soup.core.contracts import ConflictError, CreatedBy, NotFoundError, ObjectRef, ServiceUnavailableError, ValidationError
from tests.fakes import InMemoryCatalog, InMemoryFileStorage
from tests.packages import bundled_api

FileCatalog = bundled_api("tool_storage").FileCatalog

from soup_pkg_tool_storage.backends.local import LocalFileStorage  # noqa: E402

SVG = '<svg xmlns="http://www.w3.org/2000/svg"><rect width="1" height="1"/></svg>'


def _object(name: str = "orders", parents=(), created_at: str = "2025-01-01T10:00:00.000", **meta) -> ObjectRef:
    return ObjectRef(
        id=str(uuid.uuid4()),
        name=name,
        kind="table",
        created_by=CreatedBy("importer", "csv_ekg.csv", "csv_ekg"),
        parents=tuple(parents),
        created_at=created_at,
        meta=dict(meta),
    )


@pytest.fixture(params=["file-memory", "file-local", "in-memory"])
def catalog(request, tmp_path):
    if request.param == "file-memory":
        return FileCatalog(InMemoryFileStorage())
    if request.param == "file-local":
        return FileCatalog(LocalFileStorage(str(tmp_path)))
    return InMemoryCatalog()


def test_add_and_get(catalog):
    obj = _object(rows=3)

    catalog.add(obj)

    assert catalog.get(obj.id) == obj
    assert catalog.get(str(uuid.uuid4())) is None


def test_add_twice_is_a_conflict(catalog):
    obj = _object()
    catalog.add(obj)

    with pytest.raises(ConflictError):
        catalog.add(obj)


def test_list_returns_every_object(catalog):
    first, second = _object("a", created_at="2025-01-01T10:00:00.000"), _object("b", created_at="2025-01-02T10:00:00.000")
    catalog.add(second)
    catalog.add(first)

    assert sorted(obj.id for obj in catalog.list()) == sorted([first.id, second.id])


def test_children_follow_the_parents(catalog):
    root = _object("root")
    child = _object("child", parents=[root.id])
    other = _object("other")
    grandchild = _object("grandchild", parents=[child.id, other.id])
    for obj in (root, child, other, grandchild):
        catalog.add(obj)

    assert [obj.id for obj in catalog.children(root.id)] == [child.id]
    assert [obj.id for obj in catalog.children(other.id)] == [grandchild.id]
    assert catalog.children(grandchild.id) == []


def test_update_replaces_the_object(catalog):
    obj = _object(rows=1)
    catalog.add(obj)
    updated = ObjectRef.from_dict({**obj.to_dict(), "name": "renamed", "meta": {"rows": 2}})

    catalog.update(updated)

    assert catalog.get(obj.id).name == "renamed"
    assert catalog.get(obj.id).meta == {"rows": 2}


def test_update_unknown_is_not_found(catalog):
    with pytest.raises(NotFoundError):
        catalog.update(_object())


def test_remove(catalog):
    obj = _object()
    catalog.add(obj)
    catalog.set_thumbnail(obj.id, SVG)

    catalog.remove(obj.id)

    assert catalog.get(obj.id) is None
    assert catalog.list() == []
    with pytest.raises(NotFoundError):
        catalog.remove(obj.id)
    with pytest.raises(NotFoundError):
        catalog.get_thumbnail(obj.id)


def test_thumbnails(catalog):
    obj = _object()
    catalog.add(obj)

    assert catalog.get_thumbnail(obj.id) is None
    catalog.set_thumbnail(obj.id, SVG)
    assert catalog.get_thumbnail(obj.id) == SVG
    catalog.set_thumbnail(obj.id, None)
    assert catalog.get_thumbnail(obj.id) is None


def test_thumbnails_of_unknown_objects_are_not_found(catalog):
    with pytest.raises(NotFoundError):
        catalog.set_thumbnail(str(uuid.uuid4()), SVG)
    with pytest.raises(NotFoundError):
        catalog.get_thumbnail(str(uuid.uuid4()))


def test_health(catalog):
    assert catalog.health() == {"ok": True}


# ---------------------------------------------------------------------- #
# FileCatalog specifics
# ---------------------------------------------------------------------- #

def test_file_catalog_layout():
    files = InMemoryFileStorage()
    catalog = FileCatalog(files)
    obj = _object()

    catalog.add(obj)
    catalog.set_thumbnail(obj.id, SVG)

    assert files.paths == [f"_catalog/objects/{obj.id}.json", f"_catalog/thumbnails/{obj.id}.svg"]
    assert json.loads(files.read(f"_catalog/objects/{obj.id}.json")) == obj.to_dict()
    assert files.read(f"_catalog/thumbnails/{obj.id}.svg").decode("utf-8") == SVG


def test_file_catalog_persists_across_instances(tmp_path):
    obj = _object(rows=5)
    FileCatalog(LocalFileStorage(str(tmp_path))).add(obj)

    again = FileCatalog(LocalFileStorage(str(tmp_path)))

    assert again.get(obj.id) == obj
    assert (tmp_path / "_catalog" / "objects" / f"{obj.id}.json").is_file()


def test_file_catalog_lists_in_creation_order():
    catalog = FileCatalog(InMemoryFileStorage())
    later, earlier = _object("later", created_at="2025-02-01T00:00:00.000"), _object("earlier", created_at="2025-01-01T00:00:00.000")
    catalog.add(later)
    catalog.add(earlier)

    assert [obj.name for obj in catalog.list()] == ["earlier", "later"]


@pytest.mark.parametrize("object_id", ["../x", "a/b", "", "_x"])
def test_file_catalog_refuses_hostile_ids(object_id):
    catalog = FileCatalog(InMemoryFileStorage())

    with pytest.raises(ValidationError):
        catalog.get(object_id)


def test_file_catalog_refuses_meta_that_is_not_json():
    catalog = FileCatalog(InMemoryFileStorage())

    with pytest.raises(ValidationError):
        catalog.add(_object(bad=object()))
    assert catalog.list() == []


# ---------------------------------------------------------------------- #
# FileCatalog's in-memory index
# ---------------------------------------------------------------------- #

class _CountingStorage(InMemoryFileStorage):
    """InMemoryFileStorage that counts the backend calls."""

    def __init__(self) -> None:
        super().__init__()
        self.reads = 0
        self.lists = 0

    def read(self, path: str) -> bytes:
        self.reads += 1
        return super().read(path)

    def list(self, prefix: str = "") -> list[str]:
        self.lists += 1
        return super().list(prefix)


def _seeded(*objects: ObjectRef) -> _CountingStorage:
    """A volume already holding `objects`, written by another FileCatalog."""

    files = _CountingStorage()
    writer = FileCatalog(files)
    for obj in objects:
        writer.add(obj)
    files.reads = files.lists = 0
    return files


def test_the_index_is_loaded_lazily_with_one_list_and_one_read_per_object():
    root = _object("root")
    child = _object("child", parents=[root.id])
    files = _seeded(root, child)

    catalog = FileCatalog(files)
    assert (files.lists, files.reads) == (0, 0)

    assert {obj.id for obj in catalog.list()} == {root.id, child.id}
    assert (files.lists, files.reads) == (1, 2)


def test_after_the_first_list_reads_never_touch_the_backend():
    root = _object("root")
    child = _object("child", parents=[root.id])
    files = _seeded(root, child)
    catalog = FileCatalog(files)
    catalog.list()
    files.reads = files.lists = 0

    for _ in range(3):
        assert len(catalog.list()) == 2
        assert [obj.id for obj in catalog.children(root.id)] == [child.id]
        assert catalog.get(child.id) == child

    assert (files.lists, files.reads) == (0, 0)


def test_add_update_remove_keep_the_index_consistent():
    files = _CountingStorage()
    catalog = FileCatalog(files)
    root, other = _object("root"), _object("other")
    child = _object("child", parents=[root.id])
    for obj in (root, other, child):
        catalog.add(obj)
    files.reads = 0

    assert [obj.id for obj in catalog.children(root.id)] == [child.id]

    # update can move an object to other parents
    moved = ObjectRef.from_dict({**child.to_dict(), "name": "moved", "parents": [other.id]})
    catalog.update(moved)
    assert catalog.children(root.id) == []
    assert catalog.children(other.id) == [moved]
    assert catalog.get(child.id).name == "moved"

    catalog.remove(child.id)
    assert catalog.children(other.id) == []
    assert {obj.id for obj in catalog.list()} == {root.id, other.id}
    assert catalog.get(child.id) is None

    assert files.reads == 0
    # ...and what is on disk agrees with the index.
    assert {obj.id for obj in FileCatalog(files).list()} == {root.id, other.id}


def test_failed_writes_leave_the_index_unchanged():
    class _ReadOnly(InMemoryFileStorage):
        fail = False

        def write(self, path, data):
            if self.fail:
                raise PermissionError("read-only volume")
            super().write(path, data)

    files = _ReadOnly()
    catalog = FileCatalog(files)
    obj = _object()
    catalog.add(obj)
    files.fail = True

    with pytest.raises(ServiceUnavailableError):
        catalog.add(_object("new"))
    with pytest.raises(ServiceUnavailableError):
        catalog.update(ObjectRef.from_dict({**obj.to_dict(), "name": "renamed"}))

    assert [item.name for item in catalog.list()] == ["orders"]


def test_reload_reads_the_volume_again():
    files = _CountingStorage()
    catalog = FileCatalog(files)
    catalog.add(_object("mine"))
    FileCatalog(files).add(_object("written elsewhere"))

    assert [obj.name for obj in catalog.list()] == ["mine"]  # the index does not see it
    catalog.reload()

    assert sorted(obj.name for obj in catalog.list()) == ["mine", "written elsewhere"]
