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

from collections.abc import Callable, Mapping
from dataclasses import dataclass

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
    def from_env(cls, env: Mapping[str, str]) -> StorageConfig:
        return cls(
            kind=env.get("SOUP_STORAGE_KIND", DEFAULT_KIND),
            container_name=env.get("SOUP_CONTAINER_NAME", DEFAULT_CONTAINER_NAME),
            root=env.get("SOUP_LOCAL_STORAGE_ROOT", DEFAULT_ROOT),
        )


# The backends import their library only when chosen (the docker SDK is not
# needed by a local storage): hence the imports inside the factories.
def _local(config: StorageConfig) -> FileStorage:
    from .backends.local import LocalFileStorage  # noqa: PLC0415 - imported only when chosen

    return LocalFileStorage(root=config.root)


def _docker(config: StorageConfig) -> FileStorage:
    from .backends.docker import DockerVolumeStorage  # noqa: PLC0415 - imported only when chosen

    return DockerVolumeStorage(container_name=config.container_name, root=config.root)


# One factory per SOUP_STORAGE_KIND: a new backend is one more entry.
BACKENDS: dict[str, Callable[[StorageConfig], FileStorage]] = {KIND_DOCKER: _docker, KIND_LOCAL: _local}


def build_backend(config: StorageConfig) -> FileStorage:
    """:raises ValueError: unknown kind"""

    factory = BACKENDS.get(config.kind)
    if factory is None:
        raise ValueError(f"SOUP_STORAGE_KIND must be '{KIND_DOCKER}' or '{KIND_LOCAL}', got {config.kind!r}")
    return factory(config)
