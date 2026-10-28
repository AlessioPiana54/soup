"""
------------------------------------------------------------------------
File : exporter.py
Description: Exporter - like a ProM @UIExportPlugin: writes an object of
             an accepted kind to a file the user downloads.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Mapping, Sequence

from soup.core.contracts.fields import Field
from soup.core.contracts.objects import ObjectRef
from soup.core.contracts.tools import ToolAccess


class Exporter(ABC):
    """
    `id` is unique among loaded exporters; `accepts` lists object kinds;
    `extension` (e.g. ".csv") and `mime` describe the produced file;
    `requires_tools` must be among the tools its package requires or
    provides. applies() narrows `accepts` to some objects of those kinds
    (since contracts "3.1", kept in "4.0").
    """

    id: str = ""
    label: str = ""
    accepts: Sequence[str] = ()
    extension: str = ""
    mime: str = "application/octet-stream"
    requires_tools: Sequence[str] = ()

    def applies(self, obj: ObjectRef, tools: ToolAccess) -> bool:
        """
        Whether the exporter is offered for `obj`, an object of an accepted
        kind. Default: always. An exporter that does not apply is neither
        listed nor run for that object.
        """

        return True

    def fields(self, obj: ObjectRef, tools: ToolAccess) -> list[Field]:
        """Export options for `obj`. Default: none."""

        return []

    @abstractmethod
    def export(self, obj: ObjectRef, params: Mapping[str, Any], tools: ToolAccess) -> bytes:
        """`params` has already been validated against fields()."""
        raise NotImplementedError
