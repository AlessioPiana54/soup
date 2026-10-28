"""
------------------------------------------------------------------------
File : test_requirements.py
Description: soup-server/requirements.txt, the libraries of the server
             image: numpy, pandas, neo4j and docker are pinned (== or ~=),
             so pip cannot pull in a combination that fails at import
             (numpy 2.x under pandas 2.1.1: "numpy.dtype size changed");
             and the python_dependencies of every bundled package are
             satisfied by those versions, so in the image no package is
             excluded for a missing or wrong library. The check reads the
             files only (packaging.requirements), not the installed
             libraries.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

SERVER_ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS = SERVER_ROOT / "requirements.txt"
PACKAGES_ROOT = SERVER_ROOT.parent / "soup-packages"
PINNED = ("numpy", "pandas", "neo4j", "docker")


def _requirements() -> dict[str, Requirement]:
    result = {}
    for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line and not line.startswith("-"):
            requirement = Requirement(line)
            result[canonicalize_name(requirement.name)] = requirement
    return result


def _pinned_version(requirement: Requirement) -> str:
    """The version an == or ~= requirement installs at least (the one it names)."""

    [spec] = list(requirement.specifier)
    assert spec.operator in ("==", "~="), f"{requirement} is not pinned with == or ~="
    return spec.version


def _manifests() -> list[dict]:
    return [
        json.loads((path / "soup-package.json").read_text(encoding="utf-8"))
        for path in sorted(PACKAGES_ROOT.iterdir())
        if (path / "soup-package.json").exists() and not path.name.startswith("_")
    ]


def test_requirements_is_utf8_with_lf():
    data = REQUIREMENTS.read_bytes()
    data.decode("utf-8")
    assert b"\r\n" not in data


@pytest.mark.parametrize("name", PINNED)
def test_the_data_and_driver_libraries_are_pinned(name):
    requirements = _requirements()
    assert name in requirements, f"{name} missing from requirements.txt"
    _pinned_version(requirements[name])


def test_numpy_is_a_1_x_for_pandas_2_1():
    requirements = _requirements()
    assert _pinned_version(requirements["pandas"]).startswith("2.1.")
    assert _pinned_version(requirements["numpy"]).startswith("1.")


def test_python_dependencies_of_every_package_are_satisfied_by_requirements():
    requirements = _requirements()
    problems = []
    for manifest in _manifests():
        for spec in manifest.get("python_dependencies", []):
            needed = Requirement(spec)
            name = canonicalize_name(needed.name)
            if name not in requirements:
                problems.append(f"{manifest['name']}: {spec} not in requirements.txt")
                continue
            version = _pinned_version(requirements[name])
            if not needed.specifier.contains(version, prereleases=True):
                problems.append(f"{manifest['name']}: {spec} not satisfied by {requirements[name]}")
    assert problems == []


def test_the_packages_using_pandas_declare_numpy_1_x():
    for manifest in _manifests():
        names = {canonicalize_name(Requirement(spec).name): Requirement(spec) for spec in manifest.get("python_dependencies", [])}
        if "pandas" in names:
            assert "numpy" in names, f"{manifest['name']} uses pandas without declaring numpy"
            assert not names["numpy"].specifier.contains("2.0.0"), f"{manifest['name']} allows numpy 2.x"
