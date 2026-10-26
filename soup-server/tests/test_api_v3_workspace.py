"""
------------------------------------------------------------------------
File : test_api_v3_workspace.py
Description: Tests for /api/v3/objects (soup/api/workspace_routes.py):
             the provenance tree with the creating package and the
             "package missing" flag, get/update/delete (cascade, force)
             with their 400/404/409, thumbnails (SVG with a CSP, 404
             when absent, 400 when not SVG), exists?name=, and 503 when
             no package provides the catalog.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import uuid

import pytest

from tests.api_client import code_client, data_of, imported_id
from tests.mediator_doubles import FakeImporter, FakeOperation, FeaturePackage


@pytest.fixture
def setup():
    importer = FakeImporter("csv", "CSV")
    operation = FakeOperation("filter", inputs=[("log", ["table"])])
    client, engine, core = code_client(FeaturePackage("feat", importers=[importer], operations=[operation]))
    return client, engine, core


def _run_filter(client, object_id):
    response = client.post("/api/v3/operations/feat.filter/run", json={"objects": [object_id]})
    assert response.status_code == 201
    return data_of(response)[0]["id"]


def test_tree_shows_provenance_package_and_missing_flag(setup):
    client, engine, _ = setup
    log_id = imported_id(client, "feat.csv", name="log")
    child_id = _run_filter(client, log_id)

    [root] = data_of(client.get("/api/v3/objects"))
    assert root["object"]["id"] == log_id
    assert root["object"]["kind"] == "table"
    assert root["object"]["created_by"] == {"type": "importer", "contributor_id": "feat.csv", "package": "feat"}
    assert (root["package"], root["package_status"], root["package_missing"]) == ("feat", "active", False)
    [child] = root["children"]
    assert child["object"]["id"] == child_id
    assert child["object"]["parents"] == [log_id]

    engine.package_manager.disable("feat")
    [root] = data_of(client.get("/api/v3/objects"))
    assert (root["package_status"], root["package_missing"]) == ("disabled", True)


def test_get_update_and_errors(setup):
    client, _, _ = setup
    log_id = imported_id(client, "feat.csv", name="log")

    assert data_of(client.get(f"/api/v3/objects/{log_id}"))["name"] == "log"

    updated = client.put(f"/api/v3/objects/{log_id}", json={"name": "renamed", "description": "d"})
    assert updated.status_code == 200
    assert (data_of(updated)["name"], data_of(updated)["description"]) == ("renamed", "d")
    only_description = data_of(client.put(f"/api/v3/objects/{log_id}", json={"description": "e"}))
    assert (only_description["name"], only_description["description"]) == ("renamed", "e")

    assert client.put(f"/api/v3/objects/{log_id}", json={"name": "../x"}).status_code == 400
    assert client.put(f"/api/v3/objects/{log_id}", json={"name": "_hidden"}).status_code == 400
    assert client.put(f"/api/v3/objects/{log_id}", data="not json").status_code == 400
    assert client.put(f"/api/v3/objects/{log_id}", json=["a"]).status_code == 400
    assert client.get("/api/v3/objects/not-a-uuid").status_code == 400
    missing = client.get(f"/api/v3/objects/{uuid.uuid4()}")
    assert missing.status_code == 404
    assert missing.get_json()["http_status_code"] == 404


def test_delete_needs_cascade_for_children(setup):
    client, _, _ = setup
    log_id = imported_id(client, "feat.csv")
    child_id = _run_filter(client, log_id)

    conflict = client.delete(f"/api/v3/objects/{log_id}")
    assert conflict.status_code == 409
    assert data_of(conflict) == {"children": [child_id]}

    deleted = client.delete(f"/api/v3/objects/{log_id}?cascade=true")
    assert deleted.status_code == 200
    assert data_of(deleted) == {"deleted": [child_id, log_id]}
    assert data_of(client.get("/api/v3/objects")) == []
    assert client.delete(f"/api/v3/objects/{log_id}").status_code == 404


def test_delete_of_an_object_whose_package_is_disabled(setup):
    client, engine, _ = setup
    log_id = imported_id(client, "feat.csv")
    engine.package_manager.disable("feat")

    conflict = client.delete(f"/api/v3/objects/{log_id}")
    assert conflict.status_code == 409
    assert data_of(conflict)["packages"] == ["feat"]
    assert data_of(client.delete(f"/api/v3/objects/{log_id}?force=true")) == {"deleted": [log_id]}


def test_thumbnail(setup):
    client, _, _ = setup
    log_id = imported_id(client, "feat.csv")
    url = f"/api/v3/objects/{log_id}/thumbnail"

    assert client.get(url).status_code == 404
    svg = '<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>'
    assert client.put(url, data=svg, content_type="image/svg+xml").status_code == 200

    response = client.get(url)
    assert response.status_code == 200
    assert response.mimetype == "image/svg+xml"
    assert response.get_data(as_text=True) == svg
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]
    assert response.headers["X-Content-Type-Options"] == "nosniff"

    assert client.put(url, data="plain text", content_type="image/svg+xml").status_code == 400
    assert client.put(url, data="").status_code == 200
    assert client.get(url).status_code == 404
    assert client.get(f"/api/v3/objects/{uuid.uuid4()}/thumbnail").status_code == 404


def test_exists(setup):
    client, _, _ = setup
    imported_id(client, "feat.csv", name="log")

    assert data_of(client.get("/api/v3/objects/exists?name=log")) == {"name": "log", "exists": True}
    assert data_of(client.get("/api/v3/objects/exists?name=other")) == {"name": "other", "exists": False}
    assert client.get("/api/v3/objects/exists").status_code == 400


def test_workspace_without_catalog_is_503():
    client, _, _ = code_client(with_core_tools=False)

    response = client.get("/api/v3/objects")

    assert response.status_code == 503
    assert "catalog" in response.get_json()["message"]


def test_flask_404_and_405_are_unchanged(setup):
    client, _, _ = setup

    assert client.get("/api/v3/nothing-here").status_code == 404
    assert client.post("/api/v3/objects").status_code == 405
