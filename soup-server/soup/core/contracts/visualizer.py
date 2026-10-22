"""
------------------------------------------------------------------------
File : visualizer.py
Description: Visualizer - like a ProM @Visualizer: shows objects of the
             kinds it accepts. The host frontend contains no visualizer:
             `element` is the tag of a Web Component defined in the app/
             bundle of the same package, which receives the JSON returned
             by data() and calls action() for interactive requests
             (search, paging, details).
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Mapping, Sequence

from soup.core.contracts.errors import NotFoundError
from soup.core.contracts.objects import ObjectRef
from soup.core.contracts.tools import ToolAccess


class Visualizer(ABC):
    """
    `id` is unique among loaded visualizers; `accepts` lists the object
    kinds it can show; `element` is a custom-element tag (it must contain
    a "-"); `requires_tools` must be among the tools its package
    requires or provides.
    """

    id: str = ""
    label: str = ""
    accepts: Sequence[str] = ()
    element: str = ""
    requires_tools: Sequence[str] = ()

    @abstractmethod
    def data(self, obj: ObjectRef, params: Mapping[str, Any], tools: ToolAccess) -> Any:
        """The initial JSON-serializable data for the component."""
        raise NotImplementedError

    def action(self, obj: ObjectRef, name: str, params: Mapping[str, Any], tools: ToolAccess) -> Any:
        """
        Answer an interactive request `name` of the component. Default: no
        actions (an unknown action should raise NotFoundError).
        """

        raise NotFoundError(f"Visualizer '{self.id}' has no action '{name}'")
