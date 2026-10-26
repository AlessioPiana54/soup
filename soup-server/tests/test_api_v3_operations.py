"""
------------------------------------------------------------------------
File : test_api_v3_operations.py
Description: Tests for /api/v3/operations (soup/api/operation_routes.py):
             the operations applicable to a selection, their fields, a
             run with a list of ids or a {slot: id} mapping (201 with the
             created objects), and the 400/404 errors.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import uuid

import pytest

from soup.core.contracts import Field
from tests.api_client import code_client, data_of, imported_id
from tests.mediator_doubles import FakeImporter, FakeOperation, FeaturePackage


@pytest.fixture
def setup():
    by_activity = FakeOperation(
        "by_activity",
        inputs=[("log", ["table"])],
        label="Filter by activity",
        fields=lambda inputs: [Field("activity", type="select", choices=("a", "b"), required=True)],
    )
    join = FakeOperation("join", inputs=[("left", ["table"]), ("right", ["graph"])], group="Combine")
    package = FeaturePackage(
        "feat",
        importers=[FakeImporter("csv", "CSV"), FakeImporter("graph", "Graph", produces="graph")],
        operations=[by_activity, join],
    )
    client, engine, core = code_client(package)
    table_id = imported_id(client, "feat.csv", name="table")
    graph_id = imported_id(client, "feat.graph", name="graph")
    return client, core, table_id, graph_id, by_activity


def test_operations_for_a_selection(setup):
    client, _, table_id, graph_id, _ = setup

    [single] = data_of(client.get(f"/api/v3/operations?objects={table_id}"))
    assert single == {
        "id": "feat.by_activity",
        "label": "Filter by activity",
        "description": "",
        "group": "Filters",
        "inputs": [{"name": "log", "kinds": ["table"]}],
        "produces": ["table"],
        "package": "feat",
    }
    pair = data_of(client.get(f"/api/v3/operations?objects={graph_id},{table_id}"))
    assert [item["id"] for item in pair] == ["feat.join"]
    assert data_of(client.get(f"/api/v3/operations?objects={graph_id}")) == []

    assert client.get("/api/v3/operations").status_code == 400
    assert client.get("/api/v3/operations?objects=nope").status_code == 400
    assert client.get(f"/api/v3/operations?objects={uuid.uuid4()}").status_code == 404


def test_fields(setup):
    client, _, table_id, graph_id, _ = setup

    [field] = data_of(client.get(f"/api/v3/operations/feat.by_activity/fields?objects={table_id}"))
    assert (field["name"], field["type"]) == ("activity", "select")
    assert client.get(f"/api/v3/operations/feat.by_activity/fields?objects={graph_id}").status_code == 404
    assert client.get(f"/api/v3/operations/feat.ghost/fields?objects={table_id}").status_code == 404


def test_run_with_a_list_and_with_a_mapping(setup):
    client, core, table_id, graph_id, by_activity = setup

    response = client.post(
        "/api/v3/operations/feat.by_activity/run", json={"objects": [table_id], "params": {"activity": "a"}}
    )
    assert response.status_code == 201
    [created] = data_of(response)
    assert created["parents"] == [table_id]
    assert created["created_by"] == {"type": "operation", "contributor_id": "feat.by_activity", "package": "feat"}
    assert created["id"] in core.catalog.objects
    assert by_activity.runs[-1] == ({"log": table_id}, {"activity": "a"})

    joined = client.post(
        "/api/v3/operations/feat.join/run", json={"objects": {"left": table_id, "right": graph_id}}
    )
    assert joined.status_code == 201
    assert data_of(joined)[0]["parents"] == [table_id, graph_id]


def test_run_errors(setup):
    client, _, table_id, graph_id, _ = setup
    url = "/api/v3/operations/feat.by_activity/run"

    invalid = client.post(url, json={"objects": [table_id], "params": {"activity": "zzz"}})
    assert invalid.status_code == 400
    assert "activity" in invalid.get_json()["response_data"]
    assert client.post(url, json={"objects": [table_id]}).status_code == 400
    assert client.post(url, json={"objects": [table_id], "params": "x"}).status_code == 400
    assert client.post(url, json={"objects": []}).status_code == 400
    assert client.post(url, json={"objects": [1]}).status_code == 400
    assert client.post(url, data="nope", content_type="application/json").status_code == 400
    assert client.post(url, json={"objects": [graph_id], "params": {"activity": "a"}}).status_code == 404
    assert client.post("/api/v3/operations/feat.ghost/run", json={"objects": [table_id]}).status_code == 404
