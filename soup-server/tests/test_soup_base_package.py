"""
------------------------------------------------------------------------
File : test_soup_base_package.py
Description: Tests for soup-packages/soup_base, the bundled package
             drawing reports: it is discovered and active by default,
             its "Report" visualizer is offered for objects of kind
             "report" only (and for the kind itself, as the host does for
             the import preview), data() gives the blocks with name and
             description, and "Report in JSON" exports the report. The
             report objects come from an importer defined in code.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import json
import shutil

import pytest

from soup.core.contracts import report
from soup.core.packages import discover_packages
from tests.api_client import data_of, disk_client, imported_id
from tests.mediator_doubles import FakeImporter, FeaturePackage
from tests.packages import BUNDLED_PACKAGES_DIR

BLOCKS = [
    report.text("hello", title="Greeting"),
    report.table(["a", "b"], [[1, 2], [3, 4]], title="Numbers"),
]


@pytest.fixture
def client(tmp_path):
    shutil.copytree(
        BUNDLED_PACKAGES_DIR / "soup_base",
        tmp_path / "bundled" / "soup_base",
        ignore=shutil.ignore_patterns("node_modules", "__pycache__"),
    )
    reports = FeaturePackage(
        "maker",
        importers=[
            FakeImporter("report_csv", "Report", produces="report", meta={"blocks": BLOCKS}),
            FakeImporter("table_csv", "Table", produces="table"),
        ],
    )
    client, _ = disk_client(tmp_path, extra_plugins=[reports])
    return client


def test_soup_base_is_bundled_and_active_by_default():
    sources = discover_packages([BUNDLED_PACKAGES_DIR], BUNDLED_PACKAGES_DIR).sources
    assert "soup_base" in sources
    manifest = sources["soup_base"].manifest
    assert manifest.app_entry == "dist/index.js"
    assert manifest.requires_tools == ()


def test_the_report_visualizer_is_offered_for_reports_only(client):
    packages = {item["name"]: item for item in data_of(client.get("/api/v3/packages"))}
    assert packages["soup_base"]["status"] == "active"
    assert packages["soup_base"]["contributions"]["visualizers"] == ["soup_base.report"]
    assert packages["soup_base"]["contributions"]["exporters"] == ["soup_base.json"]

    report_id = imported_id(client, "maker.report_csv", name="summary")
    table_id = imported_id(client, "maker.table_csv", name="table")

    [visualizer] = data_of(client.get(f"/api/v3/objects/{report_id}/visualizers"))
    assert (visualizer["id"], visualizer["element"], visualizer["package"]) == (
        "soup_base.report", "soup-report-view", "soup_base"
    )
    assert data_of(client.get(f"/api/v3/objects/{table_id}/visualizers")) == []
    assert [item["id"] for item in data_of(client.get("/api/v3/visualizers?kind=report"))] == ["soup_base.report"]


def test_report_data_gives_the_blocks(client):
    report_id = imported_id(client, "maker.report_csv", name="summary", description="Two blocks")

    data = data_of(client.get(f"/api/v3/objects/{report_id}/visualizers/soup_base.report/data"))

    assert data == {"name": "summary", "description": "Two blocks", "blocks": BLOCKS}


def test_report_in_json(client):
    report_id = imported_id(client, "maker.report_csv", name="summary")
    table_id = imported_id(client, "maker.table_csv", name="table")

    [exporter] = data_of(client.get(f"/api/v3/objects/{report_id}/exporters"))
    assert (exporter["id"], exporter["label"], exporter["extension"], exporter["mime"], exporter["fields"]) == (
        "soup_base.json", "Report in JSON", ".json", "application/json", []
    )
    assert data_of(client.get(f"/api/v3/objects/{table_id}/exporters")) == []

    response = client.get(f"/api/v3/objects/{report_id}/export/soup_base.json")
    assert response.status_code == 200
    assert response.mimetype == "application/json"
    assert response.headers["Content-Disposition"] == "attachment; filename=summary.json"
    document = json.loads(response.data.decode("utf-8"))
    assert document["name"] == "summary"
    assert document["blocks"] == BLOCKS
    assert document["created_at"]
