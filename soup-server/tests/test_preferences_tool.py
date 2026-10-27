"""
------------------------------------------------------------------------
File : test_preferences_tool.py
Description: Tests for the tool_storage package's "preferences" tool
             (FilePreferences): JSON values in
             <root>/_catalog/preferences.json, persistent across
             instances, keys and values validated; and the bundled
             tool_storage package registering storage, catalog and
             preferences on one local backend.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import json

import pytest

from soup.core.contracts import ValidationError
from soup.core.engine import build_engine
from soup.core.settings import Settings
from tests.fakes import InMemoryFileStorage
from tests.packages import bundled_api

FilePreferences = bundled_api("tool_storage").FilePreferences

from soup_pkg_tool_storage.backends.local import LocalFileStorage  # noqa: E402


def test_unset_key_is_none():
    assert FilePreferences(InMemoryFileStorage()).get("theme") is None


def test_set_and_get_json_values():
    preferences = FilePreferences(InMemoryFileStorage())

    preferences.set("theme", "dark")
    preferences.set("onboarding", {"done": True, "steps": [1, 2]})

    assert preferences.get("theme") == "dark"
    assert preferences.get("onboarding") == {"done": True, "steps": [1, 2]}


def test_preferences_are_persistent(tmp_path):
    FilePreferences(LocalFileStorage(str(tmp_path))).set("onboarding", {"done": True})

    again = FilePreferences(LocalFileStorage(str(tmp_path)))

    assert again.get("onboarding") == {"done": True}
    stored = json.loads((tmp_path / "_catalog" / "preferences.json").read_text(encoding="utf-8"))
    assert stored == {"onboarding": {"done": True}}


@pytest.mark.parametrize("key", ["", None, 1])
def test_keys_must_be_non_empty_strings(key):
    preferences = FilePreferences(InMemoryFileStorage())

    with pytest.raises(ValidationError):
        preferences.set(key, 1)
    with pytest.raises(ValidationError):
        preferences.get(key)


def test_values_must_be_json_and_a_bad_one_changes_nothing():
    files = InMemoryFileStorage()
    preferences = FilePreferences(files)
    preferences.set("theme", "dark")

    with pytest.raises(ValidationError):
        preferences.set("bad", object())

    assert FilePreferences(files).get("theme") == "dark"
    assert FilePreferences(files).get("bad") is None


def test_health():
    assert FilePreferences(InMemoryFileStorage()).health() == {"ok": True}


def test_bundled_package_provides_the_tools_on_one_backend(tmp_path, monkeypatch):
    root = tmp_path / "volume"
    monkeypatch.setenv("SOUP_STORAGE_KIND", "local")
    monkeypatch.setenv("SOUP_LOCAL_STORAGE_ROOT", str(root))
    settings = Settings.from_env({"SOUP_PACKAGES": "tool_storage", "SOUP_INSTALLED_PACKAGES_DIR": str(tmp_path / "pkgs")})

    engine = build_engine(settings)

    assert engine.report.failed == []
    # catalog and preferences are present: nothing is missing.
    assert engine.report.warnings == []
    engine.core_tools.preferences().set("theme", "dark")
    engine.ctx.tool_registry.get("storage").space("orders").write("orders.csv", b"x")
    assert (root / "_catalog" / "preferences.json").is_file()
    assert (root / "orders" / "orders.csv").read_bytes() == b"x"
