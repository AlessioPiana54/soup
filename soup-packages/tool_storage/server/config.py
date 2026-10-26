"""
------------------------------------------------------------------------
File : config.py
Description: StorageConfig - which backend the storage tools use, read
             from the same environment variables the core used to read
             (SOUP_STORAGE_KIND, SOUP_CONTAINER_NAME,
             SOUP_LOCAL_STORAGE_ROOT), with the same defaults.
             build_backend() picks the backend.
Project : soup-packages/tool_storage
------------------------------------------------------------------------
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from soup.core.contracts import FileStorage

KIND_DOCKER = "docker"
KIND_LOCAL = "local"

DEFAULT_KIND = KIND_DOCKER
DEFAULT_CONTAINER_NAME = "soup-database"
# Memgraph's LOAD CSV reads from the volume mounted here in its container.
DEFAULT_ROOT = "/soup"


@dataclass(frozen=True)
class StorageConfig:
    kind: str = DEFAULT_KIND
    container_name: str = DEFAULT_CONTAINER_NAME
    root: str = DEFAULT_ROOT

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "StorageConfig":
        return cls(
            kind=env.get("SOUP_STORAGE_KIND", DEFAULT_KIND),
            container_name=env.get("SOUP_CONTAINER_NAME", DEFAULT_CONTAINER_NAME),
            root=env.get("SOUP_LOCAL_STORAGE_ROOT", DEFAULT_ROOT),
        )


def build_backend(config: StorageConfig) -> FileStorage:
    """:raises ValueError: unknown kind"""

    if config.kind == KIND_LOCAL:
        from .backends.local import LocalFileStorage

        return LocalFileStorage(root=config.root)
    if config.kind == KIND_DOCKER:
        from .backends.docker import DockerVolumeStorage

        return DockerVolumeStorage(container_name=config.container_name, root=config.root)
    raise ValueError(f"SOUP_STORAGE_KIND must be '{KIND_DOCKER}' or '{KIND_LOCAL}', got {config.kind!r}")
