"""
------------------------------------------------------------------------
File : test_text_and_csv_table_packages.py
Description: Tests for soup-packages/text and soup-packages/csv_table,
             the two packages built on the standard library and the
             "storage" tool only. They run with the real soup_base and
             tool_storage (local backend in a temporary folder: catalog,
             preferences and files on disk, no Docker) and without
             tool_memgraph:
             - text: .txt and .md imported into the package's storage
               space, read back through the visualizer's data and its
               "lines"/"search" actions, exported as the original file
               with its own extension and MIME type (.md, .log, also for
               objects imported without meta.extension), removed from
               the storage when the object is deleted;
             - csv_table: separator/header guessed and chosen, paging,
               sorting and filters of the "page" action, the column
               profile, the "distribution" operation producing a report
               whose parent is the table, the CSV export;
             - for a .csv the user chooses between csv_table and another
               importer of the same extension (a package defined in
               code), and with csv_ekg active a .csv can also become an
               "ekg";
             - the visualizers of "table" are not offered for a "text"
               object and vice versa.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import dataclasses
import io
import json

import pytest

from soup.core.engine import build_engine
from soup.core.settings import Settings
from tests.api_client import client_for, data_of, import_file
from tests.mediator_doubles import FakeImporter, FeaturePackage
from tests.packages import BUNDLED_PACKAGES_DIR

PACKAGES = ("soup_base", "tool_storage", "text", "csv_table")
TEXT = b"first line\nsecond line here\nthird\n"
MARKDOWN = "# Title\n\nSome *text* with \xe8.\n".encode("utf-8")
CSV = b"id;activity;cost\n1;Create;10\n2;Ship;9\n3;Create;\n4;Pay;100\n5;Ship;9\n"


def _client(tmp_path, monkeypatch, extra=(), packages=PACKAGES):
    # The packages are loaded from soup-packages/ itself, not from a copy:
    # a copy of tool_storage would be imported again as soup_pkg_tool_storage
    # and the other tests would see different classes.
    storage = tmp_path / "volume"
    monkeypatch.setenv("SOUP_STORAGE_KIND", "local")
    monkeypatch.setenv("SOUP_LOCAL_STORAGE_ROOT", str(storage))
    installed = tmp_path / "installed"
    settings = Settings(
        packages=tuple(packages),
        packages_path=(str(BUNDLED_PACKAGES_DIR), str(installed)),
        installed_packages_dir=str(installed),
    )
    engine = build_engine(settings, extra_plugins=list(extra))
    assert engine.report.failed == [], engine.report.failed
    return client_for(engine), engine, storage


@pytest.fixture
def setup(tmp_path, monkeypatch):
    return _client(tmp_path, monkeypatch)


@pytest.fixture
def client(setup):
    return setup[0]


def _import(client, importer_id, filename, content, name="data", options=None):
    response = import_file(client, importer_id, name=name, filename=filename, content=content,
                           **({"options": options} if options is not None else {}))
    assert response.status_code == 201, response.get_json()
    return data_of(response)


def _action(client, object_id, visualizer, name, params=None):
    response = client.post(f"/api/v3/objects/{object_id}/visualizers/{visualizer}/actions/{name}", json=params or {})
    return response.status_code, response.get_json()["response_data"]


# ---------------------------------------------------------------------- #
# Packages
# ---------------------------------------------------------------------- #
def test_both_packages_load_with_storage_and_no_memgraph(setup):
    client, engine, _ = setup
    assert "memgraph" not in engine.ctx.tool_registry.keys()
    packages = {item["name"]: item for item in data_of(client.get("/api/v3/packages"))}
    assert packages["text"]["status"] == packages["csv_table"]["status"] == "active"
    assert packages["text"]["contributions"]["importers"] == ["text.text"]
    assert packages["text"]["contributions"]["visualizers"] == ["text.text"]
    assert packages["text"]["contributions"]["exporters"] == ["text.original"]
    assert packages["csv_table"]["contributions"]["importers"] == ["csv_table.csv"]
    assert sorted(packages["csv_table"]["contributions"]["visualizers"]) == ["csv_table.profile", "csv_table.table"]
    assert packages["csv_table"]["contributions"]["operations"] == ["csv_table.distribution"]
    assert packages["csv_table"]["contributions"]["exporters"] == ["csv_table.csv"]

    manifest = data_of(client.get("/api/v3/frontend/manifest"))
    order = [item["name"] for item in manifest]
    assert order.index("soup_base") < order.index("text") and order.index("soup_base") < order.index("csv_table")


# ---------------------------------------------------------------------- #
# text
# ---------------------------------------------------------------------- #
def test_text_inspect_shows_the_first_50_lines(client):
    content = "\n".join(f"line {n}" for n in range(1, 81)).encode()
    inspection = data_of(client.post(
        "/api/v3/imports/inspect", data={"file": (io.BytesIO(content), "long.log"), "importer_id": "text.text"},
        content_type="multipart/form-data",
    ))
    [block] = inspection["preview"]
    assert block["type"] == "text"
    assert block["data"]["text"].splitlines() == [f"line {n}" for n in range(1, 51)]
    assert "80 in totale" in block["title"]
    assert inspection["fields"] == []


def test_import_a_txt_and_read_it_through_the_visualizer(setup):
    client, _, storage = setup
    obj = _import(client, "text.text", "notes.txt", TEXT, name="notes")
    assert obj["kind"] == "text"
    assert obj["meta"] == {
        "filename": "notes.txt", "file": obj["id"], "size": len(TEXT), "lines": 3, "encoding": "utf-8", "format": "text",
        "extension": ".txt",
    }
    assert (storage / "text" / obj["id"]).read_bytes() == TEXT

    [visualizer] = data_of(client.get(f"/api/v3/objects/{obj['id']}/visualizers"))
    assert (visualizer["id"], visualizer["element"]) == ("text.text", "soup-pkg-text-viewer")
    data = data_of(client.get(f"/api/v3/objects/{obj['id']}/visualizers/text.text/data"))
    assert data["lines"] == ["first line", "second line here", "third"]
    assert (data["format"], data["total_lines"], data["chunk"]) == ("text", 3, 500)
    assert "markdown" not in data

    assert _action(client, obj["id"], "text.text", "lines", {"from": 1, "count": 1}) == (
        200, {"from": 1, "lines": ["second line here"], "total": 3}
    )
    assert _action(client, obj["id"], "text.text", "search", {"query": "LINE"}) == (200, {
        "matches": [{"line": 1, "text": "first line"}, {"line": 2, "text": "second line here"}], "total": 2,
    })
    assert _action(client, obj["id"], "text.text", "lines", {"from": "x"})[0] == 400
    assert _action(client, obj["id"], "text.text", "unknown")[0] == 404


def test_long_files_are_read_in_blocks_of_lines(client):
    content = "\n".join(f"row {n}" for n in range(1200)).encode()
    obj = _import(client, "text.text", "big.log", content)
    data = data_of(client.get(f"/api/v3/objects/{obj['id']}/visualizers/text.text/data"))
    assert (len(data["lines"]), data["total_lines"]) == (500, 1200)
    status, block = _action(client, obj["id"], "text.text", "lines", {"from": 1000, "count": 500})
    assert status == 200
    assert (block["lines"][0], len(block["lines"])) == ("row 1000", 200)


def test_import_a_md_as_markdown(client):
    obj = _import(client, "text.text", "readme.md", MARKDOWN, name="readme")
    assert obj["meta"]["format"] == "markdown"
    data = data_of(client.get(f"/api/v3/objects/{obj['id']}/visualizers/text.text/data"))
    # Rebuilt from the cached lines: same text, "\n" line endings, no final newline.
    assert data["markdown"] == "\n".join(MARKDOWN.decode("utf-8").splitlines())


def test_latin1_fallback_and_original_file_export(client):
    content = "caff\xe8\n".encode("latin-1")
    obj = _import(client, "text.text", "old.txt", content, name="old")
    assert obj["meta"]["encoding"] == "latin-1"
    data = data_of(client.get(f"/api/v3/objects/{obj['id']}/visualizers/text.text/data"))
    assert data["lines"] == ["caff\xe8"]

    [exporter] = data_of(client.get(f"/api/v3/objects/{obj['id']}/exporters"))
    assert (exporter["id"], exporter["label"]) == ("text.original", "File originale")
    response = client.get(f"/api/v3/objects/{obj['id']}/export/text.original")
    assert response.status_code == 200
    assert response.data == content


@pytest.mark.parametrize("filename, extension, mime", [
    ("readme.md", ".md", "text/markdown"),
    ("server.log", ".log", "text/plain"),
    ("notes.txt", ".txt", "text/plain"),
    ("CHANGES.MD", ".md", "text/markdown"),
])
def test_the_original_file_is_downloaded_with_its_own_extension_and_mime(client, filename, extension, mime):
    obj = _import(client, "text.text", filename, MARKDOWN, name="doc")
    assert obj["meta"]["extension"] == extension

    response = client.get(f"/api/v3/objects/{obj['id']}/export/text.original")

    assert response.status_code == 200
    assert response.mimetype == mime
    assert f"filename=doc{extension}" in response.headers["Content-Disposition"]
    assert response.data == MARKDOWN


@pytest.mark.parametrize("legacy_meta, extension, mime", [
    ({"filename": "readme.md", "format": "markdown"}, ".md", "text/markdown"),
    ({"filename": "server.log", "format": "text"}, ".log", "text/plain"),
    ({"format": "markdown"}, ".md", "text/markdown"),
    ({}, ".txt", "text/plain"),
])
def test_objects_imported_before_meta_extension_take_it_from_their_meta(setup, legacy_meta, extension, mime):
    client, engine, _ = setup
    obj = _import(client, "text.text", "notes.txt", TEXT, name="old")
    catalog = engine.core_tools.catalog()
    stored = catalog.get(obj["id"])
    # The meta of a text imported before commit 12: no "extension".
    base = {key: value for key, value in stored.meta.items() if key not in ("extension", "filename", "format")}
    catalog.update(dataclasses.replace(stored, meta={**base, **legacy_meta}))

    response = client.get(f"/api/v3/objects/{obj['id']}/export/text.original")

    assert response.status_code == 200
    assert response.mimetype == mime
    assert f"filename=old{extension}" in response.headers["Content-Disposition"]
    assert response.data == TEXT


def test_deleting_a_text_object_removes_its_file(setup):
    client, _, storage = setup
    obj = _import(client, "text.text", "notes.txt", TEXT)
    assert (storage / "text" / obj["id"]).is_file()
    assert client.delete(f"/api/v3/objects/{obj['id']}").status_code == 200
    assert not (storage / "text" / obj["id"]).exists()


# ---------------------------------------------------------------------- #
# Choosing the importer of a .csv
# ---------------------------------------------------------------------- #
def test_for_a_csv_the_user_chooses_between_two_importers(tmp_path, monkeypatch):
    other = FakeImporter("csv", "Other CSV", produces="other.table", meta={"source": "other"})
    client, _, _ = _client(tmp_path, monkeypatch, extra=[FeaturePackage("other_csv", importers=[other])])

    importers = data_of(client.get("/api/v3/importers", query_string={"filename": "x.csv"}))
    assert sorted((item["id"], item["produces"]) for item in importers) == [
        ("csv_table.csv", "table"), ("other_csv.csv", "other.table"),
    ]
    assert [item["id"] for item in data_of(client.get("/api/v3/importers", query_string={"filename": "x.tsv"}))] == [
        "csv_table.csv"
    ]

    table = _import(client, "csv_table.csv", "x.csv", CSV, name="as-table")
    assert (table["kind"], table["created_by"]["contributor_id"]) == ("table", "csv_table.csv")
    fake = _import(client, "other_csv.csv", "x.csv", CSV, name="as-other")
    assert (fake["kind"], fake["meta"]) == ("other.table", {"source": "other"})


def test_with_csv_ekg_active_a_csv_can_also_become_an_ekg(tmp_path, monkeypatch):
    client, _, _ = _client(tmp_path, monkeypatch, packages=(*PACKAGES, "tool_memgraph", "ekg", "csv_ekg"))
    importers = data_of(client.get("/api/v3/importers", query_string={"filename": "log.csv"}))
    assert [(item["id"], item["produces"]) for item in importers] == [("csv_ekg.csv", "ekg"), ("csv_table.csv", "table")]


# ---------------------------------------------------------------------- #
# csv_table
# ---------------------------------------------------------------------- #
def test_csv_inspect_guesses_separator_and_header(client):
    inspection = data_of(client.post(
        "/api/v3/imports/inspect", data={"file": (io.BytesIO(CSV), "orders.csv"), "importer_id": "csv_table.csv"},
        content_type="multipart/form-data",
    ))
    fields = {field["name"]: field for field in inspection["fields"]}
    assert (fields["separator"]["type"], fields["separator"]["default"]) == ("select", "semicolon")
    assert [choice["value"] for choice in fields["separator"]["choices"]] == ["comma", "semicolon", "tab"]
    assert [choice["label"] for choice in fields["separator"]["choices"]] == ["virgola", "punto e virgola", "tabulazione"]
    assert (fields["header"]["type"], fields["header"]["default"]) == ("bool", True)
    [block] = inspection["preview"]
    assert block["type"] == "table"
    assert block["data"]["columns"] == ["id", "activity", "cost"]
    assert block["data"]["rows"][0] == ["1", "Create", "10"]
    assert block["data"]["total"] == 5


def test_csv_preview_follows_the_options_and_keeps_20_rows(client):
    content = b"a,b\n" + b"".join(f"{n},{n * 2}\n".encode() for n in range(30))
    preview = data_of(client.post(
        "/api/v3/imports/preview",
        data={"file": (io.BytesIO(content), "n.csv"), "importer_id": "csv_table.csv",
              "options": json.dumps({"separator": "semicolon", "header": False})},
        content_type="multipart/form-data",
    ))
    [block] = preview["blocks"]
    assert block["data"]["columns"] == ["column_1"]
    assert block["data"]["rows"][0] == ["a,b"]
    assert (len(block["data"]["rows"]), block["data"]["total"]) == (20, 31)


def test_csv_import_meta_and_tsv(client):
    obj = _import(client, "csv_table.csv", "orders.csv", CSV, name="orders")
    assert obj["meta"] == {
        "filename": "orders.csv", "file": f"{obj['id']}.csv", "columns": ["id", "activity", "cost"], "rows": 5,
        "separator": "semicolon", "header": True, "encoding": "utf-8",
    }
    tsv = _import(client, "csv_table.csv", "t.tsv", b"x\ty\n1\t2\n3\t\n", name="tsv")
    assert (tsv["meta"]["separator"], tsv["meta"]["columns"], tsv["meta"]["rows"]) == ("tab", ["x", "y"], 2)


def test_page_action_pages_sorts_and_filters(client):
    object_id = _import(client, "csv_table.csv", "orders.csv", CSV, name="orders")["id"]
    data = data_of(client.get(f"/api/v3/objects/{object_id}/visualizers/csv_table.table/data"))
    assert data == {"columns": ["id", "activity", "cost"], "total": 5, "page_size": 25}

    def page(**params):
        status, body = _action(client, object_id, "csv_table.table", "page", params)
        assert status == 200, body
        return body

    assert page(offset=2, limit=2) == {"rows": [["3", "Create", ""], ["4", "Pay", "100"]], "total": 5}
    # Numbers by value (100 after 9 and 10), stable, empty cells last in both directions.
    assert [row[2] for row in page(sort={"column": 2, "direction": "asc"})["rows"]] == ["9", "9", "10", "100", ""]
    assert [row[0] for row in page(sort={"column": 2, "direction": "desc"})["rows"]] == ["4", "1", "2", "5", "3"]
    assert page(filter=[{"column": 1, "value": "ship"}])["total"] == 2
    assert page(filter=[{"column": 1, "value": "create"}, {"column": 2, "value": "10"}])["rows"] == [["1", "Create", "10"]]
    assert page(search="pay")["rows"] == [["4", "Pay", "100"]]
    filtered = page(filter=[{"column": 1, "value": "ship"}], sort={"column": 0, "direction": "desc"}, limit=1)
    assert filtered == {"rows": [["5", "Ship", "9"]], "total": 2}

    for bad in ({"sort": {"column": 9}}, {"sort": {"column": 0, "direction": "up"}}, {"filter": [{"column": "x"}]},
                {"limit": "many"}):
        assert _action(client, object_id, "csv_table.table", "page", bad)[0] == 400


def test_profile_and_distribution_action(client):
    object_id = _import(client, "csv_table.csv", "orders.csv", CSV, name="orders")["id"]
    data = data_of(client.get(f"/api/v3/objects/{object_id}/visualizers/csv_table.profile/data"))
    assert data["rows"] == 5
    assert data["columns"][1] == {"name": "activity", "distinct": 3, "empty": 0, "examples": ["Create", "Ship", "Pay"]}
    assert data["columns"][2]["empty"] == 1

    status, result = _action(client, object_id, "csv_table.profile", "distribution", {"column": 1, "top": 2})
    assert status == 200
    assert result == {"column": "activity", "labels": ["Create", "Ship"], "counts": [2, 2], "other": 1, "total": 5}


def test_the_distribution_operation_produces_a_report_child_of_the_table(client):
    object_id = _import(client, "csv_table.csv", "orders.csv", CSV, name="orders")["id"]
    operations = data_of(client.get("/api/v3/operations", query_string={"objects": object_id}))
    assert [(item["id"], item["produces"]) for item in operations] == [("csv_table.distribution", ["report"])]
    fields = data_of(client.get("/api/v3/operations/csv_table.distribution/fields", query_string={"objects": object_id}))
    assert [(field["name"], field["type"]) for field in fields] == [("column", "column"), ("top", "number")]
    assert [choice["value"] for choice in fields[0]["choices"]] == ["id", "activity", "cost"]

    response = client.post("/api/v3/operations/csv_table.distribution/run",
                           json={"objects": [object_id], "params": {"column": "activity", "top": 2}})
    assert response.status_code == 201, response.get_json()
    [created] = data_of(response)
    assert (created["kind"], created["name"], created["parents"]) == ("report", "orders - distribuzione di activity", [object_id])
    chart, values = created["meta"]["blocks"]
    assert chart["type"] == "chart"
    assert chart["data"]["labels"] == ["Create", "Ship", "(altri)"]
    assert chart["data"]["datasets"] == [{"label": "activity", "data": [2, 2, 1]}]
    assert values["type"] == "table"
    assert values["data"]["rows"] == [["Create", 2, 40.0], ["Ship", 2, 40.0], ["(altri)", 1, 20.0]]

    # The report is drawn by soup_base.
    assert [item["id"] for item in data_of(client.get(f"/api/v3/objects/{created['id']}/visualizers"))] == ["soup_base.report"]
    bad = client.post("/api/v3/operations/csv_table.distribution/run", json={"objects": [object_id], "params": {"column": "nope"}})
    assert bad.status_code == 400


def test_column_names_with_separators_still_give_a_valid_report_name(client):
    object_id = _import(client, "csv_table.csv", "x.csv", b"in/out,b\n1,2\n", name="x")["id"]
    response = client.post("/api/v3/operations/csv_table.distribution/run",
                           json={"objects": [object_id], "params": {"column": "in/out"}})
    assert response.status_code == 201, response.get_json()
    assert data_of(response)[0]["name"] == "x - distribuzione di in out"


def test_csv_export_with_the_chosen_options(client):
    object_id = _import(client, "csv_table.csv", "orders.csv", CSV, name="orders")["id"]
    [exporter] = data_of(client.get(f"/api/v3/objects/{object_id}/exporters"))
    assert (exporter["id"], exporter["extension"]) == ("csv_table.csv", ".csv")
    assert {field["name"]: field["default"] for field in exporter["fields"]} == {"separator": "semicolon", "header": True}

    response = client.get(f"/api/v3/objects/{object_id}/export/csv_table.csv",
                          query_string={"params": json.dumps({"separator": "tab", "header": False})})
    assert response.status_code == 200, response.get_json()
    assert response.headers["Content-Disposition"] == "attachment; filename=orders.csv"
    assert response.data.decode("utf-8").splitlines()[:2] == ["1\tCreate\t10", "2\tShip\t9"]
    default = client.get(f"/api/v3/objects/{object_id}/export/csv_table.csv")
    assert default.data.decode("utf-8").splitlines()[0] == "id;activity;cost"


def test_deleting_a_table_removes_its_file(setup):
    client, _, storage = setup
    obj = _import(client, "csv_table.csv", "orders.csv", CSV)
    assert (storage / "csv_table" / f"{obj['id']}.csv").is_file()
    assert client.delete(f"/api/v3/objects/{obj['id']}").status_code == 200
    assert not (storage / "csv_table" / f"{obj['id']}.csv").exists()


# ---------------------------------------------------------------------- #
# Visualizers by kind
# ---------------------------------------------------------------------- #
def test_visualizers_are_offered_only_for_their_kind(client):
    text_id = _import(client, "text.text", "notes.txt", TEXT, name="notes")["id"]
    table_id = _import(client, "csv_table.csv", "orders.csv", CSV, name="orders")["id"]

    text_visualizers = [item["id"] for item in data_of(client.get(f"/api/v3/objects/{text_id}/visualizers"))]
    table_visualizers = [item["id"] for item in data_of(client.get(f"/api/v3/objects/{table_id}/visualizers"))]
    assert text_visualizers == ["text.text"]
    assert sorted(table_visualizers) == ["csv_table.profile", "csv_table.table"]
    assert client.get(f"/api/v3/objects/{text_id}/visualizers/csv_table.table/data").status_code in (400, 404)
    assert client.get(f"/api/v3/objects/{table_id}/visualizers/text.text/data").status_code in (400, 404)
    assert [item["id"] for item in data_of(client.get(f"/api/v3/objects/{text_id}/exporters"))] == ["text.original"]
    assert data_of(client.get("/api/v3/operations", query_string={"objects": text_id})) == []
