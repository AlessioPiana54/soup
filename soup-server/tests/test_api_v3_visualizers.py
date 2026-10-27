"""
------------------------------------------------------------------------
File : test_api_v3_visualizers.py
Description: Tests for the /api/v3 visualizer and exporter routes
             (soup/api/visualizer_routes.py): the visualizers of an
             object's kind and of a kind (?kind=, no object), their data
             (flat or ?params=<json>), actions,
             the exporters with their fields, and the export as a file
             with Content-Disposition; 400/404 errors.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import json
import uuid

import pytest

from tests.api_client import code_client, data_of, imported_id
from tests.mediator_doubles import FakeExporter, FakeImporter, FakeVisualizer, FeaturePackage


@pytest.fixture
def setup():
    package = FeaturePackage(
        "feat",
        importers=[FakeImporter("csv", "CSV")],
        visualizers=[FakeVisualizer("table_view", ["table"], label="Table"), FakeVisualizer("graph", ["graph"])],
        exporters=[FakeExporter("csv_out", ["table"])],
    )
    client, _, _ = code_client(package)
    return client, imported_id(client, "feat.csv", name="log")


def test_visualizers_of_an_object(setup):
    client, object_id = setup

    assert data_of(client.get(f"/api/v3/objects/{object_id}/visualizers")) == [{
        "id": "feat.table_view",
        "label": "Table",
        "package": "feat",
        "element": "soup-table-view",
        # Defined in code: no app part, hence no module.
        "module_url": None,
    }]
    assert client.get(f"/api/v3/objects/{uuid.uuid4()}/visualizers").status_code == 404


def test_visualizers_of_a_kind(setup):
    client, _ = setup

    assert [item["id"] for item in data_of(client.get("/api/v3/visualizers?kind=table"))] == ["feat.table_view"]
    assert [item["id"] for item in data_of(client.get("/api/v3/visualizers?kind=graph"))] == ["feat.graph"]
    assert data_of(client.get("/api/v3/visualizers?kind=report")) == []
    assert client.get("/api/v3/visualizers").status_code == 400


def test_data_with_flat_and_json_params(setup):
    client, object_id = setup
    base = f"/api/v3/objects/{object_id}/visualizers/feat.table_view/data"

    flat = data_of(client.get(f"{base}?page=2"))
    assert flat == {"visualizer": "table_view", "object": object_id, "params": {"page": "2"}}
    params = json.dumps({"page": 2, "columns": ["a"]})
    assert data_of(client.get(base, query_string={"params": params}))["params"] == {"page": 2, "columns": ["a"]}

    assert client.get(base, query_string={"params": "{bad"}).status_code == 400
    assert client.get(base, query_string={"params": "[1]"}).status_code == 400
    assert client.get(f"/api/v3/objects/{object_id}/visualizers/feat.graph/data").status_code == 404


def test_actions(setup):
    client, object_id = setup
    base = f"/api/v3/objects/{object_id}/visualizers/feat.table_view/actions"

    response = client.post(f"{base}/search", json={"q": "lo"})
    assert data_of(response) == {"matches": ["log"], "query": "lo"}
    assert data_of(client.post(f"{base}/search"))["query"] is None
    assert client.post(f"{base}/unknown", json={}).status_code == 404
    assert client.post(f"{base}/search", data="x", content_type="application/json").status_code == 400


def test_exporters_and_export(setup):
    client, object_id = setup

    [exporter] = data_of(client.get(f"/api/v3/objects/{object_id}/exporters"))
    assert (exporter["id"], exporter["package"], exporter["extension"], exporter["mime"]) == (
        "feat.csv_out", "feat", ".csv", "text/csv"
    )
    assert exporter["fields"][0]["name"] == "separator"

    response = client.get(f"/api/v3/objects/{object_id}/export/feat.csv_out?separator=;")
    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    assert response.headers["Content-Disposition"] == "attachment; filename=log.csv"
    assert response.data == b"log;table"

    assert client.get(f"/api/v3/objects/{object_id}/export/feat.csv_out?separator=|").status_code == 400
    assert client.get(f"/api/v3/objects/{object_id}/export/feat.ghost").status_code == 404
