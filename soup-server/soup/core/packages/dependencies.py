"""
------------------------------------------------------------------------
File : dependencies.py
Description: Checks a manifest's python_dependencies against the
             libraries installed on the server (importlib.metadata).
             Nothing is installed at runtime: a missing or too old
             library excludes the package, with a message saying which
             one and what to do.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import importlib.metadata as importlib_metadata
from typing import Callable, Optional

from packaging.requirements import Requirement

from soup.core.packages.manifest import PackageManifest

VersionLookup = Callable[[str], Optional[str]]


def installed_version(distribution: str) -> Optional[str]:
    try:
        return importlib_metadata.version(distribution)
    except importlib_metadata.PackageNotFoundError:
        return None


def python_dependency_problems(manifest: PackageManifest, lookup: VersionLookup = installed_version) -> list[str]:
    """One message per unsatisfied requirement; [] when all are satisfied."""

    problems = []
    for spec in manifest.python_dependencies:
        requirement = Requirement(spec)
        if requirement.marker is not None and not requirement.marker.evaluate():
            continue
        version = lookup(requirement.name)
        if version is None:
            problems.append(f"'{spec}' (not installed)")
        elif requirement.specifier and not requirement.specifier.contains(version, prereleases=True):
            problems.append(f"'{spec}' (installed: {version})")
    return problems
