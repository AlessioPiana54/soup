"""
------------------------------------------------------------------------
File : archive.py
Description: Safe extraction of a package zip. Limits on the uploaded
             size, the number of entries, the total extracted size and
             the compression ratio (zip bombs); every entry name is
             checked before anything is written (absolute paths, drive
             letters, "..", backslashes and symbolic links are refused:
             zip slip). The manifest may sit at the root of the zip or
             inside a single top-level folder.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import io
import shutil
import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import BinaryIO

from soup.core.contracts import ValidationError
from soup.core.packages.manifest import MANIFEST_FILE, is_safe_relative_path


@dataclass(frozen=True)
class ArchiveLimits:
    max_archive_bytes: int = 50 * 1024 * 1024
    max_extracted_bytes: int = 200 * 1024 * 1024
    max_entries: int = 2000
    max_ratio: int = 100
    # Small files may compress very well legitimately; the ratio is
    # checked only above this size.
    ratio_min_bytes: int = 1024 * 1024


DEFAULT_LIMITS = ArchiveLimits()


def read_limited(stream: BinaryIO, limit: int) -> bytes:
    """Read at most `limit` bytes. :raises ValidationError: the stream is longer"""

    data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValidationError(f"Package archive is larger than {limit // (1024 * 1024)} MB")
    return data


def extract_package_zip(stream: BinaryIO, destination: Path, limits: ArchiveLimits = DEFAULT_LIMITS) -> Path:
    """
    Extract into `destination` (which must not exist yet) and return the
    folder holding soup-package.json.
    :raises ValidationError: not a zip, a limit exceeded, a hostile entry
        name, or no manifest at the expected place
    """

    data = read_limited(stream, limits.max_archive_bytes)
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise ValidationError("Package archive is not a valid zip file") from None

    with archive:
        infos = archive.infolist()
        _check_entries(infos, limits)
        root = _package_root(infos)

        destination.mkdir(parents=True)
        base = destination.resolve()
        try:
            for info in infos:
                target = (destination / info.filename).resolve()
                if target != base and base not in target.parents:  # defensive: names are already checked
                    raise ValidationError(f"Archive entry escapes the package folder: {info.filename!r}")
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, open(target, "wb") as output:
                    shutil.copyfileobj(source, output)
        except BaseException:
            shutil.rmtree(destination, ignore_errors=True)
            raise

    return destination / root if root else destination


def _check_entries(infos: list[zipfile.ZipInfo], limits: ArchiveLimits) -> None:
    if len(infos) > limits.max_entries:
        raise ValidationError(f"Package archive has more than {limits.max_entries} entries")
    total = 0
    for info in infos:
        name = info.filename
        if not is_safe_relative_path(name.rstrip("/")):
            raise ValidationError(f"Package archive contains a forbidden path: {name!r}")
        mode = info.external_attr >> 16
        if stat.S_ISLNK(mode):
            raise ValidationError(f"Package archive contains a symbolic link: {name!r}")
        total += info.file_size
        if total > limits.max_extracted_bytes:
            raise ValidationError(
                f"Package archive expands to more than {limits.max_extracted_bytes // (1024 * 1024)} MB"
            )
        if (
            info.file_size > limits.ratio_min_bytes
            and info.compress_size
            and info.file_size / info.compress_size > limits.max_ratio
        ):
            raise ValidationError(f"Package archive entry {name!r} is suspiciously compressed")


def _package_root(infos: list[zipfile.ZipInfo]) -> str:
    names = {PurePosixPath(info.filename.rstrip("/")) for info in infos if info.filename.rstrip("/")}
    if PurePosixPath(MANIFEST_FILE) in names:
        return ""
    tops = {name.parts[0] for name in names}
    if len(tops) == 1:
        top = next(iter(tops))
        if PurePosixPath(top, MANIFEST_FILE) in names:
            return top
    raise ValidationError(
        f"Package archive must contain {MANIFEST_FILE} at its root or inside a single top-level folder"
    )
