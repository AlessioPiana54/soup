"""
------------------------------------------------------------------------
File : discovery.py
Description: Finds packages on disk: every sub-folder of the folders in
             SOUP_PACKAGES_PATH that holds a soup-package.json. Entries
             starting with "_" or "." are skipped (the installed-packages
             folder keeps its state file and staging area there). When
             two folders hold a package with the same name, the higher
             version wins; on a tie the earlier folder in the path wins.
             Invalid manifests are returned as failures, never raised.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from soup.core.contracts import ValidationError
from soup.core.packages.manifest import MANIFEST_FILE, PackageManifest, load_manifest

ORIGIN_BUNDLED = "bundled"
ORIGIN_INSTALLED = "installed"


@dataclass(frozen=True)
class PackageSource:
    """A package found on disk: its manifest, its folder and where it comes from."""

    manifest: PackageManifest
    path: Path
    origin: str

    @property
    def name(self) -> str:
        return self.manifest.name


@dataclass
class DiscoveryResult:
    sources: dict[str, PackageSource] = field(default_factory=dict)
    # (folder name, error): folders whose manifest is invalid.
    failures: list[tuple[str, Exception]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def discover_packages(paths: Iterable[str | Path], installed_dir: str | Path) -> DiscoveryResult:
    result = DiscoveryResult()
    installed = Path(installed_dir).resolve()

    for root in paths:
        root_path = Path(root)
        if not root_path.is_dir():
            continue
        origin = ORIGIN_INSTALLED if root_path.resolve() == installed else ORIGIN_BUNDLED
        for entry in sorted(root_path.iterdir(), key=lambda item: item.name):
            if entry.name.startswith(("_", ".")) or not entry.is_dir() or not (entry / MANIFEST_FILE).is_file():
                continue
            try:
                manifest = load_manifest(entry)
            except ValidationError as exc:
                result.failures.append((entry.name, exc))
                continue
            if manifest.name != entry.name:
                result.failures.append((entry.name, ValidationError(
                    f"Package folder '{entry.name}' holds package '{manifest.name}': the folder must be named after it"
                )))
                continue
            _add(result, PackageSource(manifest, entry, origin))

    return result


def _add(result: DiscoveryResult, source: PackageSource) -> None:
    existing = result.sources.get(source.name)
    if existing is None:
        result.sources[source.name] = source
        return
    winner, loser = (
        (source, existing)
        if source.manifest.parsed_version > existing.manifest.parsed_version
        else (existing, source)
    )
    result.sources[source.name] = winner
    result.warnings.append(
        f"Package '{source.name}' found twice: using {winner.manifest.version} from '{winner.path}', "
        f"ignoring {loser.manifest.version} from '{loser.path}'"
    )
