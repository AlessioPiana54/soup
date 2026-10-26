"""
------------------------------------------------------------------------
File : config.py
Description: MemgraphConfig - where the memgraph tool connects, read
             from the same environment variables the core used to read
             (MEMGRAPH_HOST, MEMGRAPH_PORT), with the same defaults.
Project : soup-packages/tool_memgraph
------------------------------------------------------------------------
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

DEFAULT_HOST = "memgraph"
DEFAULT_PORT = 7687


@dataclass(frozen=True)
class MemgraphConfig:
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT

    @property
    def uri(self) -> str:
        return f"bolt://{self.host}:{self.port}"

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "MemgraphConfig":
        return cls(
            host=env.get("MEMGRAPH_HOST", DEFAULT_HOST),
            port=int(env.get("MEMGRAPH_PORT", DEFAULT_PORT)),
        )
