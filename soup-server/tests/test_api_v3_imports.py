"""
------------------------------------------------------------------------
File : test_api_v3_imports.py
Description: Tests for the /api/v3 import routes (soup/api/
             import_routes.py): the importers offered for a file name
             (several for the same extension, module_url only with a
             config_element), inspect, preview and import with their
             400/404/503 errors, and the SOUP_MAX_UPLOAD_MB limit, which
             applies to /api/v3 only.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import io

import pytest

from soup.core.contracts import ValidationError
from tests.api_client import code_client, data_of, disk_client, import_file
from tests.mediator_doubles import FakeImporter, FeaturePackage
from tests.package_builder import FEATURE_PLUGIN, write_package


def _multipart(importer_id="feat.csv", content=b"a,b\n", filename="log.csv", **form):
    return {"file": (io.BytesIO(content), filename), "importer_id": importer_id, **form}


@pytest.fixture
def setup():
    tables = FakeImporter("csv", "Tables")
    graph = FakeImporter("graph", "As graph", produces="graph")
    xes = FakeImporter("xes", "XES", extensions=(".xes",))
    client, engine, core = code_client(FeaturePackage("feat", importers=[tables, graph, xes]))
    return client, engine, core, tables


def test_importers_for_a_file_name(setup):
    client, _, _, _ = setup

    importers = data_of(client.get("/api/v3/importers?filename=log.csv"))

    assert [item["id"] for item in importers] == ["feat.graph", "feat.csv"]
    graph = importers[0]
    assert graph == {
        "id": "feat.graph",
        "label": "As graph",
        "description": "",
        "extensions": [".csv"],
        "produces": "graph",
        "package": "feat",
        "config_element": None,
        "module_url": None,
    }
    assert data_of(client.get("/api/v3/importers?filename=log.json")) == []
    assert client.get("/api/v3/importers").status_code == 400


def test_importer_with_a_config_element_has_the_module_url_of_its_package(tmp_path):
    source = FEATURE_PLUGIN.replace('    label = "CSV"\n', '    label = "CSV"\n    config_element = "feat-config"\n')
    write_package(
        tmp_path / "bundled", "feat", plugin_source=source,
        app_entry="dist/index.js", app_files={"dist/index.js": b"export {};"},
    )
    client, _ = disk_client(tmp_path)

    [importer] = data_of(client.get("/api/v3/importers?filename=x.csv"))

    assert importer["config_element"] == "feat-config"
    assert importer["module_url"] == "/api/v3/packages/feat/app/index.js"


def test_inspect_preview_and_import(setup):
    client, _, core, tables = setup

    inspected = client.post("/api/v3/imports/inspect", data=_multipart(), content_type="multipart/form-data")
    assert inspected.status_code == 200
    assert data_of(inspected)["preview"][0]["data"]["text"] == "csv:a,b\n"
    assert data_of(inspected)["fields"][0]["name"] == "separator"

    preview = client.post(
        "/api/v3/imports/preview",
        data=_multipart(options='{"separator": ";"}'),
        content_type="multipart/form-data",
    )
    assert data_of(preview)["blocks"][0]["data"]["text"] == "csv separator=;"

    created = import_file(client, "feat.csv", name="log", description="first", options={"separator": ";"})
    assert created.status_code == 201
    obj = data_of(created)
    assert (obj["name"], obj["kind"], obj["description"], obj["meta"]) == ("log", "table", "first", {"rows": 2})
    assert obj["created_by"]["contributor_id"] == "feat.csv"
    assert obj["id"] in core.catalog.objects


def test_import_errors(setup):
    client, _, core, tables = setup

    no_file = client.post("/api/v3/imports", data={"importer_id": "feat.csv", "name": "x"},
                          content_type="multipart/form-data")
    assert no_file.status_code == 400
    assert no_file.get_json()["http_status_code"] == 400
    no_importer = client.post("/api/v3/imports", data=_multipart(importer_id="", name="x"),
                              content_type="multipart/form-data")
    assert no_importer.status_code == 400
    assert import_file(client, "feat.csv", options="{not json").status_code == 400
    assert import_file(client, "feat.csv", options="[1]").status_code == 400
    assert import_file(client, "feat.csv", name="").status_code == 400
    assert import_file(client, "feat.csv", name="a/b").status_code == 400
    assert import_file(client, "feat.xes", filename="log.csv").status_code == 400
    assert import_file(client, "feat.ghost").status_code == 404
    assert import_file(client, "ghost").status_code == 404

    tables.fail_with = ValidationError("bad separator")
    rejected = import_file(client, "feat.csv")
    assert rejected.status_code == 400
    assert rejected.get_json()["message"] == "bad separator"
    assert core.catalog.objects == {}


def test_import_without_catalog_is_503():
    client, _, _ = code_client(FeaturePackage("feat", importers=[FakeImporter("csv", "CSV")]), with_core_tools=False)

    assert import_file(client, "feat.csv").status_code == 503


def test_upload_limit_applies_to_v3():
    client, _, _ = code_client(FeaturePackage("feat", importers=[FakeImporter("csv", "CSV")]), max_upload_mb=1)
    big = b"x" * (1024 * 1024 + 1)

    assert import_file(client, "feat.csv", content=big).status_code == 413
    assert import_file(client, "feat.csv", content=b"small").status_code == 201
