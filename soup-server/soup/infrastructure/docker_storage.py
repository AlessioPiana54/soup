"""
------------------------------------------------------------------------
File : docker_storage.py
Description: FileStorage adapter writing into the SOUP Docker volume via
             the Docker SDK's put_archive()/get_archive(), building the
             tar archive entirely in memory (io.BytesIO) - unlike the
             legacy Models/docker_file_manager_model.py (not modified by
             this session), which round-trips through temporary files on
             the host. DockerException is let through (not swallowed) so
             callers can handle it, instead of the legacy
             DockerService.get_container_id_s() behaviour of catching only
             subprocess.CalledProcessError and returning None.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import io
import tarfile

import docker
from docker.errors import DockerException

from soup.core.contracts import FileStorage


class DockerVolumeStorage(FileStorage):
    def __init__(self, container_name: str = "soup-database", root: str = "/soup"):
        self._container_name = container_name
        self._root = root.rstrip("/") or "/"

    def _container(self):
        try:
            client = docker.from_env()
            return client.containers.get(self._container_name)
        except DockerException:
            raise
        except Exception as exc:  # pragma: no cover - defensive, docker-py specific
            raise DockerException(f"Unable to reach container '{self._container_name}': {exc}") from exc

    def _full_path(self, path: str) -> str:
        return f"{self._root}/{path.lstrip('/')}"

    def write(self, path: str, data: bytes) -> None:
        container = self._container()
        full_path = self._full_path(path)
        directory, _, file_name = full_path.rpartition("/")
        directory = directory or "/"

        try:
            container.exec_run(["sh", "-c", f"mkdir -p {directory}"])

            tarstream = io.BytesIO()
            with tarfile.open(fileobj=tarstream, mode="w") as tar:
                info = tarfile.TarInfo(name=file_name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
            tarstream.seek(0)

            success = container.put_archive(directory, tarstream)
            if not success:
                raise DockerException(f"put_archive failed for '{full_path}'")
        except DockerException:
            raise
        except Exception as exc:
            raise DockerException(f"Error writing '{full_path}': {exc}") from exc

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
                    raise DockerException(f"'{full_path}' is empty in the container archive")
                extracted = tar.extractfile(members[0])
                return extracted.read() if extracted is not None else b""
        except DockerException:
            raise
        except Exception as exc:
            raise DockerException(f"Error reading '{full_path}': {exc}") from exc

    def exists(self, path: str) -> bool:
        container = self._container()
        full_path = self._full_path(path)
        result = container.exec_run(["sh", "-c", f"test -e {full_path}"])
        return result.exit_code == 0

    def delete(self, path: str) -> None:
        container = self._container()
        full_path = self._full_path(path)
        result = container.exec_run(["rm", "-rf", full_path])
        if result.exit_code != 0:
            raise DockerException(f"Unable to delete '{full_path}'")

    def list(self, prefix: str = "") -> list[str]:
        container = self._container()
        full_path = self._full_path(prefix) if prefix else self._root
        result = container.exec_run(["sh", "-c", f"ls -1 {full_path}"])
        if result.exit_code != 0:
            return []
        return [line for line in result.output.decode("utf-8").splitlines() if line]
