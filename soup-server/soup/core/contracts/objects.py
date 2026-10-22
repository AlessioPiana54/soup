"""
------------------------------------------------------------------------
File : objects.py
Description: Typed objects - everything the user works on. An importer
             creates objects from files, an operation creates objects
             from other objects (its `parents`), visualizers and
             exporters bind to an object's `kind`. The core routes on
             `kind` and on `created_by` (who must dispose of the object);
             what the data is and where it lives is the contributing
             package's business, recorded in `meta`.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

CREATED_BY_IMPORTER = "importer"
CREATED_BY_OPERATION = "operation"
CREATOR_TYPES = (CREATED_BY_IMPORTER, CREATED_BY_OPERATION)


@dataclass(frozen=True)
class CreatedBy:
    """The contribution (and its package) that created an object."""

    type: str
    contributor_id: str
    package: str

    def __post_init__(self) -> None:
        if self.type not in CREATOR_TYPES:
            raise ValueError(f"CreatedBy.type must be one of {CREATOR_TYPES}, got {self.type!r}")

    def to_dict(self) -> dict[str, str]:
        return {"type": self.type, "contributor_id": self.contributor_id, "package": self.package}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CreatedBy":
        return cls(str(data["type"]), str(data["contributor_id"]), str(data["package"]))


@dataclass(frozen=True)
class ObjectRef:
    """
    What the catalog knows about one object. `id` is a uuid assigned by
    the core; `name` is the user-facing, validated name (not unique);
    `parents` are the ids of the objects an operation consumed to
    produce this one (empty for imported objects); `created_at` uses the
    ProcessTimer format ("2025-01-01T10:00:00.123"); `meta` is what the
    contributor returned (JSON-serializable).
    """

    id: str
    name: str
    kind: str
    created_by: CreatedBy
    parents: tuple[str, ...] = ()
    created_at: str = ""
    description: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "parents", tuple(self.parents))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "created_by": self.created_by.to_dict(),
            "parents": list(self.parents),
            "created_at": self.created_at,
            "description": self.description,
            "meta": dict(self.meta),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ObjectRef":
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            kind=str(data["kind"]),
            created_by=CreatedBy.from_dict(data["created_by"]),
            parents=tuple(data.get("parents") or ()),
            created_at=str(data.get("created_at") or ""),
            description=str(data.get("description") or ""),
            meta=dict(data.get("meta") or {}),
        )


@dataclass
class ObjectDraft:
    """
    What an operation returns for each object it produced; the core
    assigns id, created_by, parents and created_at and registers it in
    the catalog. A draft of kind "report" must carry meta["blocks"]
    (see report.py).
    """

    name: str
    kind: str
    meta: dict[str, Any] = field(default_factory=dict)
    description: str = ""
