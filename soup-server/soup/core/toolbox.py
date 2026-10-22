"""
------------------------------------------------------------------------
File : toolbox.py
Description: ToolBox - the host-side implementation of ToolAccess: the
             tools one package (or one of its contributions) may use,
             i.e. only the ones it declared. Asking for anything else is
             a programming error of the package and fails loudly, even if
             the tool is loaded.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from typing import Iterable, TypeVar

from soup.core.contracts import ServiceUnavailableError, Tool, ToolNotDeclaredError
from soup.core.registry import Registry

T = TypeVar("T", bound=Tool)


class ToolBox:
    def __init__(self, tools: Registry[Tool], allowed: Iterable[str], owner: str):
        self._tools = tools
        self._allowed = frozenset(allowed)
        self._owner = owner

    @property
    def names(self) -> frozenset[str]:
        return self._allowed

    def get(self, name: str) -> Tool:
        """
        :raises ToolNotDeclaredError: `name` was not declared by the owner
        :raises ServiceUnavailableError: declared, but no package provides it
        """

        if name not in self._allowed:
            raise ToolNotDeclaredError(self._owner, name)
        tool = self._tools.get(name)
        if tool is None:
            raise ServiceUnavailableError(f"Tool '{name}' is not available: no loaded package provides it")
        return tool

    def typed(self, name: str, expected: type[T]) -> T:
        tool = self.get(name)
        if not isinstance(tool, expected):
            raise ServiceUnavailableError(f"Tool '{name}' is a {type(tool).__name__}, not a {expected.__name__}")
        return tool

    def has(self, name: str) -> bool:
        return name in self._allowed and name in self._tools

    def __getitem__(self, name: str) -> Tool:
        return self.get(name)
