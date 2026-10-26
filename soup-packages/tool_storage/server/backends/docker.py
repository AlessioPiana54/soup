"""
------------------------------------------------------------------------
File : docker.py
Description: FileStorage backend writing into the SOUP Docker volume via
             the Docker SDK's put_archive()/get_archive() (moved here
             from soup/infrastructure/docker_storage.py), building the
             tar archive entirely in memory (io.BytesIO) - unlike the
             legacy Models/docker_file_manager_model.py, which
             round-trips through temporary files on the host (C12).
             Commands run in the container as argv lists, never through
             "sh -c" with the path spliced in. DockerException is
             translated at this boundary (C35): a missing file becomes
             FileNotFoundError, anything else ServiceUnavailableError
             (503), instead of the legacy
             DockerService.get_container_id_s() behaviour of catching only
             subprocess.CalledProcessError and returning None.
Project : soup-packages/tool_storage
------------------------------------------------------------------------
"""

from __future__ import annotations

import io
import posixpath
import tarfile
from typing import Any, Callable

import docker
from docker.errors import DockerException, NotFound

from soup.core.contracts import FileStorage, ServiceUnavailableError


class DockerVolumeStorage(FileStorage):
    """`client_factory` builds the Docker client (docker.from_env by default; tests pass a fake)."""

    def __init__(
        self,
        container_name: str = "soup-database",
        root: str = "/soup",
        client_factory: Callable[[], Any] = docker.from_env,
    ):
        self._container_name = container_name
        self._root = root.rstrip("/") or "/"
        self._client_factory = client_factory

    def _container(self):
        try:
            client = self._client_factory()
            return client.containers.get(self._container_name)
        except DockerException as exc:
            raise self._unavailable(f"Unable to reach container '{self._container_name}'", exc) from exc

    def _unavailable(self, what: str, exc: Exception) -> ServiceUnavailableError:
        return ServiceUnavailableError(f"File storage is not available: {what}: {exc}")

    def _full_path(self, path: str) -> str:
        relative = path.strip("/")
        if ".." in relative.split("/"):
            raise ValueError(f"Path {path!r} is outside the storage root")
        return posixpath.join(self._root, relative) if relative else self._root

    def write(self, path: str, data: bytes) -> None:
        container = self._container()
        full_path = self._full_path(path)
        directory, _, file_name = full_path.rpartition("/")
        directory = directory or "/"

        try:
            result = container.exec_run(["mkdir", "-p", directory])
            if result.exit_code != 0:
                raise DockerException(f"mkdir failed for '{directory}'")

            tarstream = io.BytesIO()
            with tarfile.open(fileobj=tarstream, mode="w") as tar:
                info = tarfile.TarInfo(name=file_name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
            tarstream.seek(0)

            if not container.put_archive(directory, tarstream):
                raise DockerException(f"put_archive failed for '{full_path}'")
        except DockerException as exc:
            raise self._unavailable(f"error writing '{full_path}'", exc) from exc

    def read(self, path: str) -> bytes:
        container = self._container()
        full_path = self._full_path(path)

        try:
            stream, _ = container.get_archive(full_path)
            tarstream = io.BytesIO()
            for chunk in stream:
                tarstream.write(chunk)
            tarstream.seek(0)

            with tarfile.open(fileobj=tarstream, mode="r") as tar:
                members = tar.getmembers()
                if not members:
                    raise FileNotFoundError(full_path)
                extracted = tar.extractfile(members[0])
                return extracted.read() if extracted is not None else b""
        except NotFound:
            raise FileNotFoundError(full_path) from None
        except DockerException as exc:
            raise self._unavailable(f"error reading '{full_path}'", exc) from exc
        except tarfile.TarError as exc:
            raise self._unavailable(f"error reading '{full_path}'", exc) from exc

    def exists(self, path: str) -> bool:
        return self._exec(["test", "-e", self._full_path(path)], "checking").exit_code == 0

    def delete(self, path: str) -> None:
        full_path = self._full_path(path)
        if full_path == self._root:
            raise ValueError("Refusing to delete the storage root")
        if self._exec(["rm", "-rf", full_path], "deleting").exit_code != 0:
            raise self._unavailable(f"unable to delete '{full_path}'", DockerException("rm failed"))

    def list(self, prefix: str = "") -> list[str]:
        result = self._exec(["ls", "-1", self._full_path(prefix)], "listing")
        if result.exit_code != 0:
            return []
        return [line for line in result.output.decode("utf-8").splitlines() if line]

    def _exec(self, argv: list[str], what: str):
        container = self._container()
        try:
            return container.exec_run(argv)
        except DockerException as exc:
            raise self._unavailable(f"error {what} '{argv[-1]}'", exc) from exc
