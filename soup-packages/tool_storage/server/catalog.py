"""
------------------------------------------------------------------------
File : catalog.py
Description: FileCatalog - the "catalog" tool: the objects of the
             workspace, one JSON file each (ObjectRef.to_dict) in
             <root>/_catalog/objects/<id>.json, with optional SVG
             previews in <root>/_catalog/thumbnails/<id>.svg. children(id)
             (the objects listing id among their parents) is what
             provenance and deletion are built on. Follows the Catalog
             port's error contract.
             The files are the source of truth, but reads are served by
             an in-memory index (objects by id, children by parent id),
             loaded lazily on first use with one list + one read per
             file, and kept in step by add/update/remove after each write
             to disk; get/list/children never touch the backend again.
             reload() reads the volume again (e.g. after it was changed
             from outside). One lock guards the index and the writes, so
             two requests never interleave an add/update/remove.
Project : soup-packages/tool_storage
------------------------------------------------------------------------
"""

from __future__ import annotations

import builtins
import json
import threading
from typing import Any

from soup.core.contracts import (
    Catalog,
    ConflictError,
    FileStorage,
    NotFoundError,
    ObjectRef,
    ValidationError,
    validate_name,
)

from .storage import guard_os_errors

CATALOG_DIR = "_catalog"
OBJECTS_DIR = f"{CATALOG_DIR}/objects"
THUMBNAILS_DIR = f"{CATALOG_DIR}/thumbnails"

_OBJECT_SUFFIX = ".json"


class FileCatalog(Catalog):
    def __init__(self, backend: FileStorage):
        self._backend = backend
        self._lock = threading.RLock()
        # None until the first read; then object id -> ObjectRef and
        # parent id -> ids of the objects listing it among their parents.
        self._objects: dict[str, ObjectRef] | None = None
        self._children: dict[str, set[str]] = {}

    def health(self) -> dict[str, Any]:
        try:
            self._backend.list(OBJECTS_DIR)
        except Exception as exc:  # noqa: BLE001 - health() must not raise
            return {"ok": False, "error": str(exc)}
        return {"ok": True}

    # ------------------------------------------------------------------ #
    # Objects
    # ------------------------------------------------------------------ #
    def add(self, obj: ObjectRef) -> None:
        with self._lock:
            objects = self._index()
            if obj.id in objects:
                raise ConflictError(f"Object '{obj.id}' already exists")
            self._write(obj)
            self._put(obj)

    def get(self, object_id: str) -> ObjectRef | None:
        validate_name(object_id, label="Object id")
        with self._lock:
            return self._index().get(object_id)

    def list(self) -> builtins.list[ObjectRef]:
        with self._lock:
            objects = list(self._index().values())
        return sorted(objects, key=lambda item: (item.created_at, item.id))

    def children(self, object_id: str) -> builtins.list[ObjectRef]:
        with self._lock:
            objects = self._index()
            children = [objects[child_id] for child_id in self._children.get(object_id, ())]
        return sorted(children, key=lambda item: (item.created_at, item.id))

    def update(self, obj: ObjectRef) -> None:
        with self._lock:
            self._require(obj.id)
            self._write(obj)
            self._drop(obj.id)
            self._put(obj)

    def remove(self, object_id: str) -> None:
        with self._lock:
            self._require(object_id)
            guard_os_errors(f"Object '{object_id}'", self._backend.delete, self._object_path(object_id))
            guard_os_errors(f"Thumbnail '{object_id}'", self._backend.delete, self._thumbnail_path(object_id))
            self._drop(object_id)

    def reload(self) -> None:
        """Forget the index and read the volume again."""

        with self._lock:
            self._objects = None
            self._index()

    # ------------------------------------------------------------------ #
    # Thumbnails (read from disk: the index holds only the ObjectRefs)
    # ------------------------------------------------------------------ #
    def get_thumbnail(self, object_id: str) -> str | None:
        self._require(object_id)
        path = self._thumbnail_path(object_id)
        if not guard_os_errors(f"Thumbnail '{object_id}'", self._backend.exists, path):
            return None
        return guard_os_errors(f"Thumbnail '{object_id}'", self._backend.read, path).decode("utf-8")

    def set_thumbnail(self, object_id: str, svg: str | None) -> None:
        with self._lock:
            self._require(object_id)
            path = self._thumbnail_path(object_id)
            if svg is None:
                guard_os_errors(f"Thumbnail '{object_id}'", self._backend.delete, path)
            elif not isinstance(svg, str):
                raise ValidationError("A thumbnail must be SVG markup (a string)")
            else:
                guard_os_errors(f"Thumbnail '{object_id}'", self._backend.write, path, svg.encode("utf-8"))

    # ------------------------------------------------------------------ #
    # Index (call with the lock held)
    # ------------------------------------------------------------------ #
    def _index(self) -> dict[str, ObjectRef]:
        if self._objects is None:
            objects: dict[str, ObjectRef] = {}
            for file_name in guard_os_errors("Catalog", self._backend.list, OBJECTS_DIR):
                if not file_name.endswith(_OBJECT_SUFFIX):
                    continue
                path = f"{OBJECTS_DIR}/{file_name}"
                raw = guard_os_errors(f"Object file '{file_name}'", self._backend.read, path)
                obj = ObjectRef.from_dict(json.loads(raw.decode("utf-8")))
                objects[obj.id] = obj
            self._objects = objects
            self._children = {}
            for obj in objects.values():
                self._link(obj)
        return self._objects

    def _put(self, obj: ObjectRef) -> None:
        self._index()[obj.id] = obj
        self._link(obj)

    def _link(self, obj: ObjectRef) -> None:
        for parent_id in obj.parents:
            self._children.setdefault(parent_id, set()).add(obj.id)

    def _drop(self, object_id: str) -> None:
        obj = self._index().pop(object_id, None)
        if obj is None:
            return
        for parent_id in obj.parents:
            siblings = self._children.get(parent_id)
            if siblings is not None:
                siblings.discard(object_id)
                if not siblings:
                    del self._children[parent_id]

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _object_path(self, object_id: str) -> str:
        return f"{OBJECTS_DIR}/{validate_name(object_id, label='Object id')}{_OBJECT_SUFFIX}"

    def _thumbnail_path(self, object_id: str) -> str:
        return f"{THUMBNAILS_DIR}/{validate_name(object_id, label='Object id')}.svg"

    def _require(self, object_id: str) -> None:
        validate_name(object_id, label="Object id")
        with self._lock:
            if object_id not in self._index():
                raise NotFoundError(f"Object '{object_id}' not found")

    def _write(self, obj: ObjectRef) -> None:
        try:
            payload = json.dumps(obj.to_dict(), indent=2, ensure_ascii=False).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"Object '{obj.id}' is not JSON-serializable: {exc}") from exc
        guard_os_errors(f"Object '{obj.id}'", self._backend.write, self._object_path(obj.id), payload)
