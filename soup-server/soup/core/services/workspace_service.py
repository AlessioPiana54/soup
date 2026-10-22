"""
------------------------------------------------------------------------
File : workspace_service.py
Description: WorkspaceService - the objects of the workspace as a tree
             of provenance (an operation's outputs under the objects it
             consumed), plus rename, description, thumbnail and delete.
             Deleting an object publishes "object.before_delete", asks
             the contributor that created it (importer or operation) to
             dispose of its data, then removes it from the catalog. An
             object with children is deleted only with cascade=True
             (children first), otherwise 409.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from typing import Any, Optional

from soup.core.contracts import (
    CREATED_BY_IMPORTER,
    ConflictError,
    Importer,
    ObjectRef,
    Operation,
    ValidationError,
    validate_name,
)
from soup.core.event_bus import EventBus
from soup.core.events import OBJECT_BEFORE_DELETE
from soup.core.registry import Registry
from soup.core.services.core_tools import CoreTools

_LOGGER = logging.getLogger("soup.workspace")


@dataclass
class WorkspaceNode:
    object: ObjectRef
    children: list["WorkspaceNode"] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"object": self.object.to_dict(), "children": [child.to_dict() for child in self.children]}


def _order(obj: ObjectRef) -> tuple[str, str, str]:
    return (obj.created_at, obj.name.lower(), obj.id)


class WorkspaceService:
    def __init__(
        self,
        importers: Registry[Importer],
        operations: Registry[Operation],
        core_tools: CoreTools,
        event_bus: EventBus,
    ):
        self._importers = importers
        self._operations = operations
        self._core_tools = core_tools
        self._event_bus = event_bus

    def list(self) -> list[WorkspaceNode]:
        """
        Roots are objects with no parent in the catalog. An object with
        several parents (an operation with several inputs) appears under
        each of them.
        """

        objects = sorted(self._core_tools.catalog().list(), key=_order)
        ids = {obj.id for obj in objects}
        children: dict[str, list[ObjectRef]] = {}
        roots = []
        for obj in objects:
            known_parents = [parent for parent in dict.fromkeys(obj.parents) if parent in ids]
            if not known_parents:
                roots.append(obj)
            for parent in known_parents:
                children.setdefault(parent, []).append(obj)

        def build(obj: ObjectRef, path: frozenset[str]) -> WorkspaceNode:
            node = WorkspaceNode(obj)
            for child in children.get(obj.id, ()):
                if child.id not in path:  # defensive: provenance should never loop
                    node.children.append(build(child, path | {child.id}))
            return node

        return [build(root, frozenset({root.id})) for root in roots]

    def get(self, object_id: str) -> ObjectRef:
        return self._core_tools.object(object_id)

    def rename(self, object_id: str, name: str) -> ObjectRef:
        validate_name(name)
        return self._update(replace(self.get(object_id), name=name))

    def update_description(self, object_id: str, description: str) -> ObjectRef:
        if not isinstance(description, str):
            raise ValidationError("Description must be a string")
        return self._update(replace(self.get(object_id), description=description))

    def get_thumbnail(self, object_id: str) -> Optional[str]:
        ref = self.get(object_id)
        return self._core_tools.catalog().get_thumbnail(ref.id)

    def set_thumbnail(self, object_id: str, svg: Optional[str]) -> None:
        if svg is not None and not isinstance(svg, str):
            raise ValidationError("Thumbnail must be SVG text")
        ref = self.get(object_id)
        self._core_tools.catalog().set_thumbnail(ref.id, svg)

    def delete(self, object_id: str, cascade: bool = False) -> list[str]:
        """
        Return the ids deleted, children before parents.
        :raises ConflictError: the object has children and cascade is False
        """

        root = self.get(object_id)
        catalog = self._core_tools.catalog()
        direct_children = catalog.children(root.id)
        if direct_children and not cascade:
            raise ConflictError(
                f"Object '{root.name}' has {len(direct_children)} derived object(s); delete them first or use cascade",
                details={"children": [child.id for child in direct_children]},
            )

        ordered: list[ObjectRef] = []
        seen: set[str] = set()

        def visit(obj: ObjectRef) -> None:
            seen.add(obj.id)
            for child in sorted(catalog.children(obj.id), key=_order):
                if child.id not in seen:
                    visit(child)
            ordered.append(obj)

        visit(root)
        for obj in ordered:
            self._delete_one(obj)
        return [obj.id for obj in ordered]

    # ------------------------------------------------------------------ #
    def _update(self, ref: ObjectRef) -> ObjectRef:
        self._core_tools.catalog().update(ref)
        return ref

    def _delete_one(self, obj: ObjectRef) -> None:
        self._event_bus.publish(OBJECT_BEFORE_DELETE, {"object": obj.to_dict()})
        creator = obj.created_by
        registry: Registry[Any] = self._importers if creator.type == CREATED_BY_IMPORTER else self._operations
        contributor = registry.get(creator.contributor_id)
        if contributor is None or not self._core_tools.available(contributor.requires_tools):
            _LOGGER.warning(
                "%s '%s' (package '%s') is not loaded: data of object '%s' was not disposed of",
                creator.type, creator.contributor_id, creator.package, obj.id,
            )
        else:
            tools = self._core_tools.toolbox(f"{creator.type} '{contributor.id}'", contributor.requires_tools)
            contributor.dispose(obj, tools)
        self._core_tools.catalog().remove(obj.id)
