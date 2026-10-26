"""
------------------------------------------------------------------------
File : test_template_package.py
Description: Tests for soup-packages/_template, the example package to
             copy: its folder is skipped by the discovery (leading "_"),
             and once copied as "template" it loads, its importer reads a
             .txt file (inspect, preview, import with max_lines), its
             visualizer answers data and the "stats" action, and its
             bundle is served and listed in the frontend manifest. The
             bundle is a stand-in written by the test (no Node needed).
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import io
import json
import shutil

import pytest

from soup.core.packages import discover_packages
from tests.api_client import data_of, disk_client
from tests.packages import BUNDLED_PACKAGES_DIR

TEMPLATE_DIR = BUNDLED_PACKAGES_DIR / "_template"
TEXT = b"first line\nsecond line here\nthird\n"


def _file(content: bytes = TEXT, filename: str = "notes.txt"):
    return (io.BytesIO(content), filename)


@pytest.fixture
def template(tmp_path):
    bundled = tmp_path / "bundled"
    shutil.copytree(
        TEMPLATE_DIR, bundled / "template", ignore=shutil.ignore_patterns("node_modules", "dist", "__pycache__")
    )
    dist = bundled / "template" / "app" / "dist"
    dist.mkdir()
    (dist / "index.js").write_text("customElements.define('soup-template-text', class extends HTMLElement {});\n")
    client, _ = disk_client(tmp_path)
    return client


def test_the_template_folder_is_not_discovered():
    names = discover_packages([BUNDLED_PACKAGES_DIR], BUNDLED_PACKAGES_DIR).sources
    assert "template" not in names


def test_the_copied_template_loads_with_its_importer_and_visualizer(template):
    packages = {item["name"]: item for item in data_of(template.get("/api/v3/packages"))}
    assert packages["template"]["status"] == "active"
    assert packages["template"]["contributions"]["importers"] == ["template.text"]
    assert packages["template"]["contributions"]["visualizers"] == ["template.text"]

    importers = data_of(template.get("/api/v3/importers", query_string={"filename": "notes.txt"}))
    assert [(item["id"], item["produces"], item["package"]) for item in importers] == [
        ("template.text", "template.text", "template")
    ]
    assert data_of(template.get("/api/v3/importers", query_string={"filename": "notes.csv"})) == []


def test_inspect_preview_and_import(template):
    inspection = data_of(template.post(
        "/api/v3/imports/inspect", data={"file": _file(), "importer_id": "template.text"},
        content_type="multipart/form-data",
    ))
    assert inspection["preview"][0]["type"] == "text"
    assert inspection["preview"][0]["data"]["text"].startswith("first line")
    assert [(field["name"], field["type"], field["default"]) for field in inspection["fields"]] == [
        ("max_lines", "number", 200)
    ]

    preview = data_of(template.post(
        "/api/v3/imports/preview",
        data={"file": _file(), "importer_id": "template.text", "options": json.dumps({"max_lines": 2})},
        content_type="multipart/form-data",
    ))
    assert preview["blocks"][0]["data"]["items"] == [
        {"key": "lines in the file", "value": 3}, {"key": "lines kept", "value": 2}
    ]

    response = template.post(
        "/api/v3/imports",
        data={"file": _file(), "importer_id": "template.text", "name": "notes", "options": json.dumps({"max_lines": 2})},
        content_type="multipart/form-data",
    )
    assert response.status_code == 201, response.get_json()
    obj = data_of(response)
    assert obj["kind"] == "template.text"
    assert obj["meta"] == {"filename": "notes.txt", "total_lines": 3, "lines": ["first line", "second line here"]}


def test_visualizer_data_action_and_bundle(template):
    response = template.post(
        "/api/v3/imports", data={"file": _file(), "importer_id": "template.text", "name": "notes"},
        content_type="multipart/form-data",
    )
    object_id = data_of(response)["id"]

    visualizers = data_of(template.get(f"/api/v3/objects/{object_id}/visualizers"))
    assert visualizers == [{
        "id": "template.text",
        "label": "Text",
        "package": "template",
        "element": "soup-template-text",
        "module_url": "/api/v3/packages/template/app/index.js",
    }]
    base = f"/api/v3/objects/{object_id}/visualizers/template.text"
    assert data_of(template.get(f"{base}/data"))["lines"] == ["first line", "second line here", "third"]
    assert data_of(template.post(f"{base}/actions/stats", json={})) == {"lines": 3, "words": 6, "characters": 31}
    assert template.post(f"{base}/actions/unknown", json={}).status_code == 404

    manifest = data_of(template.get("/api/v3/frontend/manifest"))
    assert {"name": "template", "version": "1.0.0", "module_url": "/api/v3/packages/template/app/index.js",
            "requires": []} in manifest
    bundle = template.get("/api/v3/packages/template/app/index.js")
    assert bundle.status_code == 200
    assert bundle.mimetype == "text/javascript"
