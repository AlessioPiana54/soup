"""
------------------------------------------------------------------------
File : importer.py
Description: Importer - turns a file chosen by the user into an object.
             Several importers may accept the same extension with
             different results: the user picks one. The importer decides
             the object kind (`produces`) and how the data is kept (split
             into tables, loaded into Memgraph, stored as a file, ...),
             using only the tools it declares. Inspection is what it
             shows before the import: a preview (blocks, see report.py)
             and the fields of the generic import form - or, with
             `config_element`, the tag of a Web Component from its package
             that replaces that form.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence

from soup.core.contracts.fields import Field
from soup.core.contracts.objects import ObjectRef
from soup.core.contracts.tools import ToolAccess
from soup.core.contracts.upload import Upload


@dataclass(frozen=True)
class Inspection:
    """What an importer shows about a file before importing it."""

    preview: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    fields: tuple[Field, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "preview", tuple(self.preview))
        object.__setattr__(self, "fields", tuple(self.fields))

    def to_dict(self) -> dict[str, Any]:
        return {"preview": [dict(block) for block in self.preview], "fields": [f.to_dict() for f in self.fields]}


class Importer(ABC):
    """
    `id` is unique among loaded importers; `extensions` (e.g. (".csv",))
    drive the default accepts(); `produces` is the kind of the objects it
    creates; `requires_tools` must be among the tools its package
    requires or provides.
    """

    id: str = ""
    label: str = ""
    description: str = ""
    extensions: Sequence[str] = ()
    produces: str = ""
    requires_tools: Sequence[str] = ()
    config_element: Optional[str] = None

    def accepts(self, filename: str) -> bool:
        """Default: match by file extension. Override for content sniffing."""

        lowered = filename.lower()
        return any(lowered.endswith(extension.lower()) for extension in self.extensions)

    @abstractmethod
    def inspect(self, upload: Upload, tools: ToolAccess) -> Inspection:
        raise NotImplementedError

    def preview(self, upload: Upload, options: Mapping[str, Any], tools: ToolAccess) -> list[dict[str, Any]]:
        """
        Optional: an updated preview while the user fills in the form
        (e.g. after choosing a separator). Default: no preview.
        """

        return []

    @abstractmethod
    def import_(self, upload: Upload, obj: ObjectRef, options: Mapping[str, Any], tools: ToolAccess) -> dict[str, Any]:
        """
        Store `upload` as `obj` (id, name, kind and created_by already
        set) and return the object's meta.
        """
        raise NotImplementedError

    @abstractmethod
    def dispose(self, obj: ObjectRef, tools: ToolAccess) -> None:
        """
        Remove everything import_() created for `obj`. Also called after a
        failed import_() (with empty meta), so it must tolerate partial
        state.
        """
        raise NotImplementedError
