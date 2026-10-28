"""
------------------------------------------------------------------------
File : operation.py
Description: Operation - like a ProM @Plugin: takes one or more objects
             of given kinds (`inputs`) and produces new objects of the
             kinds listed in `produces` (a filtered log, a model, a
             "report"...). It is offered only when the selected objects
             match its inputs. The core assigns ids, parents and
             created_by to what run() returns.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from soup.core.contracts.fields import Field
from soup.core.contracts.objects import ObjectDraft, ObjectRef
from soup.core.contracts.tools import ToolAccess


@dataclass(frozen=True)
class OperationInput:
    """One input slot: its `name` (key in `inputs`) and the kinds it accepts."""

    name: str
    kinds: tuple[str, ...]

    def __post_init__(self) -> None:
        kinds = (self.kinds,) if isinstance(self.kinds, str) else tuple(self.kinds)
        object.__setattr__(self, "kinds", kinds)
        if not self.name or not kinds:
            raise ValueError("OperationInput needs a name and at least one kind")

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "kinds": list(self.kinds)}


class Operation(ABC):
    """
    `id` is unique among loaded operations; `group` gathers related
    operations in the interface (e.g. "Filters", "Statistics");
    `inputs` lists the input slots (at least one); `produces` lists the
    kinds of the objects run() may return; `requires_tools` must be
    among the tools its package requires or provides. In fields() and
    run(), `inputs` maps each slot name to the chosen ObjectRef.
    """

    id: str = ""
    label: str = ""
    description: str = ""
    group: str = ""
    inputs: Sequence[OperationInput] = ()
    produces: tuple[str, ...] = ()
    requires_tools: Sequence[str] = ()

    def fields(self, inputs: Mapping[str, ObjectRef], tools: ToolAccess) -> list[Field]:
        """
        The parameters for these inputs (choices may come from them,
        e.g. the activities of a log). Default: none.
        """

        return []

    @abstractmethod
    def run(self, inputs: Mapping[str, ObjectRef], params: Mapping[str, Any], tools: ToolAccess) -> list[ObjectDraft]:
        """`params` has already been validated against fields()."""
        raise NotImplementedError

    def dispose(self, obj: ObjectRef, tools: ToolAccess) -> None:
        """
        Remove what run() stored for `obj` outside the catalog (e.g. graph
        nodes). Default: nothing to remove (everything is in `meta`).
        """

        return None
