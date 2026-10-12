"""
------------------------------------------------------------------------
File : settings.py
Description: Engine settings, read from the environment with explicit
             defaults - replacing the hard-coded `debug` flag that used
             to live in Shared/support_config.py.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping, Optional

DEFAULT_STRICT = False
DEFAULT_STORAGE_KIND = "docker"  # "docker" | "local"
DEFAULT_MEMGRAPH_HOST = "memgraph"
DEFAULT_MEMGRAPH_PORT = 7687
DEFAULT_CONTAINER_NAME = "soup-database"
DEFAULT_LOCAL_STORAGE_ROOT = "/soup"

_TRUE_VALUES = {"1", "true", "yes", "on"}


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _as_bool(value: Optional[str], default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in _TRUE_VALUES


@dataclass(frozen=True)
class Settings:
    plugins: tuple[str, ...] = ()
    strict: bool = DEFAULT_STRICT
    storage_kind: str = DEFAULT_STORAGE_KIND
    memgraph_host: str = DEFAULT_MEMGRAPH_HOST
    memgraph_port: int = DEFAULT_MEMGRAPH_PORT
    container_name: str = DEFAULT_CONTAINER_NAME
    local_storage_root: str = DEFAULT_LOCAL_STORAGE_ROOT

    @classmethod
    def from_env(cls, env: Optional[Mapping[str, str]] = None) -> "Settings":
        """Build Settings from environment variables, with explicit defaults for each."""

        source = os.environ if env is None else env

        return cls(
            plugins=_split_csv(source.get("SOUP_PLUGINS", "")),
            strict=_as_bool(source.get("SOUP_STRICT"), DEFAULT_STRICT),
            storage_kind=source.get("SOUP_STORAGE_KIND", DEFAULT_STORAGE_KIND),
            memgraph_host=source.get("MEMGRAPH_HOST", DEFAULT_MEMGRAPH_HOST),
            memgraph_port=int(source.get("MEMGRAPH_PORT", DEFAULT_MEMGRAPH_PORT)),
            container_name=source.get("SOUP_CONTAINER_NAME", DEFAULT_CONTAINER_NAME),
            local_storage_root=source.get("SOUP_LOCAL_STORAGE_ROOT", DEFAULT_LOCAL_STORAGE_ROOT),
        )
