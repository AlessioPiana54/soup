"""
------------------------------------------------------------------------
File : ports.py
Description: FileStorage, the stable port (abstract interface) of file
             storage, implemented in soup-packages/tool_storage (its
             backends and each storage namespace are FileStorage). The
             graph database port (GraphDatabase) and the Query value
             object live in soup-packages/tool_memgraph, with the tool
             that implements them: the core knows nothing of Cypher.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import builtins
from abc import ABC, abstractmethod


class FileStorage(ABC):
    """Port for reading/writing dataset files, independent of where they live."""

    @abstractmethod
    def read(self, path: str) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def write(self, path: str, data: bytes) -> None:
        raise NotImplementedError

    @abstractmethod
    def exists(self, path: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def delete(self, path: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def list(self, prefix: str = "") -> builtins.list[str]:
        raise NotImplementedError
