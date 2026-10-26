"""
------------------------------------------------------------------------
File : test_package_manifest.py
Description: Tests for the soup-package.json format
             (soup.core.packages.manifest): a valid manifest, and every
             kind of invalid one reported with one message per field.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import pytest

from soup.core.contracts import ValidationError
from soup.core.packages import load_manifest, parse_manifest
from tests.package_builder import manifest_for, write_package
from tests.packages import BUNDLED_PACKAGES_DIR


def test_valid_manifest_is_parsed(tmp_path):
    folder = write_package(tmp_path, "alpha", requires=["beta"], python_dependencies=["pytest>=7"])

    manifest = load_manifest(folder)

    assert manifest.name == "alpha"
    assert manifest.version == "1.0.0"
    assert manifest.requires == ("beta",)
    assert manifest.python_dependencies == ("pytest>=7",)
    assert manifest.server_module == "server"
    assert manifest.server_plugin == "plugin:Plugin"
    assert manifest.app_entry is None
    assert manifest.module_name == "soup_pkg_alpha"


def test_bundled_packages_have_valid_manifests():
    for name in ("csv_reader", "causal_df"):
        assert load_manifest(BUNDLED_PACKAGES_DIR / name).name == name


def test_app_entry_is_optional_but_must_stay_inside_the_package():
    data = manifest_for("alpha")
    assert parse_manifest({**data, "app": {"entry": "dist/index.js"}}).app_entry == "dist/index.js"
    with pytest.raises(ValidationError) as error:
        parse_manifest({**data, "app": {"entry": "../../etc/passwd"}})
    assert "app" in error.value.details["fields"]


def test_app_entry_must_be_inside_dist():
    data = manifest_for("alpha")
    for entry in ("index.js", "src/index.ts", "dist/", "distribution/index.js"):
        with pytest.raises(ValidationError) as error:
            parse_manifest({**data, "app": {"entry": entry}})
        assert "dist" in error.value.details["fields"]["app"]


@pytest.mark.parametrize(
    ("change", "field"),
    [
        ({"name": ""}, "name"),
        ({"name": "Has-Dash"}, "name"),
        ({"name": "_hidden"}, "name"),
        ({"name": "a/b"}, "name"),
        ({"version": "not a version"}, "version"),
        ({"api_version": 2}, "api_version"),
        ({"requires": "beta"}, "requires"),
        ({"requires": ["alpha"]}, "requires"),
        ({"requires_tools": [1]}, "requires_tools"),
        ({"python_dependencies": ["pandas >>> 2"]}, "python_dependencies"),
        ({"server": None}, "server"),
        ({"server": {"module": "../server", "plugin": "plugin:Plugin"}}, "server"),
        ({"server": {"module": "server", "plugin": "plugin"}}, "server"),
    ],
)
def test_invalid_fields_are_reported_by_name(change, field):
    with pytest.raises(ValidationError) as error:
        parse_manifest({**manifest_for("alpha"), **change})
    assert field in error.value.details["fields"]
    assert error.value.http_status_code == 400


def test_several_problems_are_reported_at_once():
    with pytest.raises(ValidationError) as error:
        parse_manifest({"name": "alpha"})
    assert {"version", "api_version", "server"} <= set(error.value.details["fields"])


def test_server_module_must_exist(tmp_path):
    folder = write_package(tmp_path, "alpha")
    (folder / "server" / "__init__.py").unlink()
    with pytest.raises(ValidationError, match="not found"):
        load_manifest(folder)


def test_missing_or_broken_manifest_file(tmp_path):
    with pytest.raises(ValidationError, match="Missing soup-package.json"):
        load_manifest(tmp_path)
    (tmp_path / "soup-package.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(ValidationError, match="not valid JSON"):
        load_manifest(tmp_path)
