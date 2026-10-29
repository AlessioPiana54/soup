"""
------------------------------------------------------------------------
File : test_ocel_package.py
Description: Tests for the ocel package through /api/v3, with the real
             tool_storage (local backend in a temporary folder) and
             FakeDatabase as Memgraph (no Docker):
             - for a .json or .jsonocel file both importers are offered;
               inspect gives the summary and the first events, and a
               non-conforming file is a 400 with the reason;
             - "come tabelle": kind "ocel_tables" without a single
               Memgraph query, its own visualizers (no EKG one), paging,
               type filter, search and sort of the "page" action, the
               summary, the OCEL 2.0 JSON export with the extension of
               the imported file, the folder removed on delete;
             - "come EKG": kind "ekg" with an entity type per object type,
               the qualifiers and object-object relationships declared
               missing from the graph, the visualizers of ekg_views;
             - "Scomponi in EKG": an "ekg" child of the tables, with the
               same dataset as the importer;
             - installed from a zip with the test client (ocel not on the
               server before): importers, visualizers, operation and
               exporter available at once, its bundle served.
Project : soup-packages/ocel
------------------------------------------------------------------------
"""

from __future__ import annotations

import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

from soup.core.engine import build_engine
from soup.core.settings import Settings
from tests.api_client import client_for, data_of, import_file
from tests.fakes import FakeDatabase, ekg_engine, use_database
from tests.packages import BUNDLED_PACKAGES_DIR, bundled_plugin

FIXTURE = Path(__file__).parent / "fixtures" / "orders.json"
DATA = FIXTURE.read_bytes()
REQUIRED = ("tool_memgraph", "tool_storage", "soup_base", "ekg", "ekg_views")
PACKAGES = (*REQUIRED, "ocel")
EKG_VISUALIZERS = ["ekg_views.graph", "ekg_views.queries", "ekg_views.stats"]


@pytest.fixture
def setup(tmp_path, monkeypatch):
    db = FakeDatabase()
    engine = ekg_engine(tmp_path, monkeypatch, packages=PACKAGES, db=db)
    assert engine.report.failed == [], engine.report.failed
    return client_for(engine), engine, db, tmp_path / "volume"


@pytest.fixture
def client(setup):
    return setup[0]


def _import(client, importer, name="orders", filename="orders.json", content=DATA):
    response = import_file(client, importer, name=name, filename=filename, content=content)
    assert response.status_code == 201, response.get_json()
    return data_of(response)


def _inspect(client, importer, content=DATA, filename="orders.json"):
    return client.post(
        "/api/v3/imports/inspect", data={"file": (io.BytesIO(content), filename), "importer_id": importer},
        content_type="multipart/form-data",
    )


def _page(client, object_id, **params):
    response = client.post(f"/api/v3/objects/{object_id}/visualizers/ocel.tables/actions/page", json=params)
    return response.status_code, response.get_json()["response_data"]


def _visualizers(client, object_id):
    return sorted(item["id"] for item in data_of(client.get(f"/api/v3/objects/{object_id}/visualizers")))


# ---------------------------------------------------------------------- #
# Choosing the importer, inspect
# ---------------------------------------------------------------------- #
@pytest.mark.parametrize("filename", ["orders.json", "ORDERS.JSONOCEL"])
def test_for_an_ocel_file_the_user_chooses_between_tables_and_ekg(client, filename):
    importers = data_of(client.get("/api/v3/importers", query_string={"filename": filename}))

    assert sorted((item["id"], item["produces"]) for item in importers) == [
        ("ocel.ekg", "ekg"), ("ocel.tables", "ocel_tables"),
    ]
    ekg = next(item for item in importers if item["id"] == "ocel.ekg")
    assert "qualifier" in ekg["description"] and "oggetto-oggetto" in ekg["description"]


@pytest.mark.parametrize("importer", ["ocel.tables", "ocel.ekg"])
def test_inspect_shows_the_summary_and_the_first_events(setup, importer):
    client, _engine, db, _volume = setup
    inspection = data_of(_inspect(client, importer))

    summary, events = inspection["preview"]
    assert summary["type"] == "keyvalue"
    assert summary["data"]["items"] == [
        {"key": "eventi", "value": 5}, {"key": "oggetti", "value": 6},
        {"key": "tipi di evento", "value": 3}, {"key": "tipi di oggetto", "value": 3},
    ]
    assert events["type"] == "table"
    assert events["data"]["columns"] == ["event_id", "event_type", "time", "resource", "amount"]
    assert events["data"]["rows"][0] == ["e1", "place order", "2023-01-01T09:00:00Z", "Alice", None]
    assert events["data"]["total"] == 5
    assert inspection["fields"] == []
    assert db.received_queries == []


@pytest.mark.parametrize("importer", ["ocel.tables", "ocel.ekg"])
def test_a_non_conforming_file_is_a_400_with_the_reason(client, importer):
    broken = DATA.replace(b'"objectId": "c1", "qualifier": "customer"', b'"objectId": "c9", "qualifier": "customer"', 1)

    for content, reason in ((b"{oops", "not JSON"), (broken, "object 'c9' is not among the objects")):
        inspected = _inspect(client, importer, content)
        imported = import_file(client, importer, name="bad", filename="bad.json", content=content)
        for response in (inspected, imported):
            assert response.status_code == 400
            assert "Not a valid OCEL 2.0 JSON file" in response.get_json()["message"]
            assert reason in response.get_json()["message"]
    assert data_of(client.get("/api/v3/objects")) == []


# ---------------------------------------------------------------------- #
# As tables
# ---------------------------------------------------------------------- #
def test_import_as_tables_needs_no_memgraph_and_offers_only_its_own_visualizers(setup):
    client, engine, db, volume = setup

    obj = _import(client, "ocel.tables")

    assert obj["kind"] == "ocel_tables"
    assert obj["meta"]["extension"] == ".json"
    assert obj["meta"]["counts"]["object_objects"] == 4
    assert db.received_queries == []
    importer = next(entry for entry in engine.ctx.importers.entries() if entry.key == "ocel.tables").item
    assert tuple(importer.requires_tools) == ("storage",)
    assert sorted(path.name for path in (volume / "ocel" / obj["id"]).iterdir()) == [
        "event_objects.json", "events.json", "object_attributes.json", "object_objects.json", "objects.json",
        "types.json",
    ]
    assert _visualizers(client, obj["id"]) == ["ocel.summary", "ocel.tables"]
    assert not set(EKG_VISUALIZERS) & set(_visualizers(client, obj["id"]))
    operations = data_of(client.get("/api/v3/operations", query_string={"objects": obj["id"]}))
    assert [item["id"] for item in operations] == ["ocel.to_ekg"]


def test_the_tables_visualizer_pages_filters_searches_and_sorts_on_the_server(client):
    obj = _import(client, "ocel.tables")

    data = data_of(client.get(f"/api/v3/objects/{obj['id']}/visualizers/ocel.tables/data"))
    assert data["page_size"] == 25
    assert [(tab["key"], tab["label"], tab["total"]) for tab in data["tables"]] == [
        ("events", "Eventi", 5), ("objects", "Oggetti", 6),
        ("event_objects", "Relazioni evento-oggetto", 12), ("object_objects", "Relazioni oggetto-oggetto", 4),
    ]
    assert data["tables"][0]["types"] == ["place order", "pick item", "pay order"]
    assert data["tables"][2]["columns"] == ["event_id", "event_type", "object_id", "object_type", "qualifier"]
    assert data["tables"][3]["types"] == ["order", "item", "customer"]

    status, page = _page(client, obj["id"], table="events", offset=1, limit=2)
    assert status == 200
    assert (page["total"], [row[0] for row in page["rows"]]) == (5, ["e2", "e3"])

    status, page = _page(client, obj["id"], table="events", type="pick item")
    assert (page["total"], [row[0] for row in page["rows"]]) == (2, ["e3", "e4"])

    status, page = _page(client, obj["id"], table="event_objects", type="customer")
    assert [row[:3] for row in page["rows"]] == [["e1", "place order", "c1"], ["e2", "place order", "c1"]]

    # Object-object: the type of either end.
    status, page = _page(client, obj["id"], table="object_objects", type="customer")
    assert page["rows"] == [["o1", "order", "c1", "customer", "ordered by"]]

    status, page = _page(client, obj["id"], table="objects", search="ADA")
    assert [row[0] for row in page["rows"]] == ["c1"]

    status, page = _page(client, obj["id"], table="objects", sort={"column": 2, "direction": "desc"})
    assert [row[0] for row in page["rows"]] == ["o1", "o2", "i1", "i2", "i3", "c1"]

    for params in ({"table": "object_attributes"}, {"table": "nope"}, {"table": "events", "offset": -1},
                   {"table": "events", "sort": {"column": 99}}, {"table": "events", "type": 3}):
        assert _page(client, obj["id"], **params)[0] == 400
    response = client.post(f"/api/v3/objects/{obj['id']}/visualizers/ocel.tables/actions/explode", json={})
    assert response.status_code == 404


def test_the_summary_has_the_counts_and_the_events_per_type(client):
    obj = _import(client, "ocel.tables")

    data = data_of(client.get(f"/api/v3/objects/{obj['id']}/visualizers/ocel.summary/data"))

    assert data["counts"] == {
        "events": 5, "objects": 6, "event_types": 3, "object_types": 3, "event_objects": 12, "object_objects": 4,
    }
    assert data["events_per_type"] == {"place order": 2, "pick item": 2, "pay order": 1}
    assert data["objects_per_type"] == {"order": 2, "item": 3, "customer": 1}


@pytest.mark.parametrize("filename, extension", [("orders.json", ".json"), ("orders.jsonocel", ".jsonocel")])
def test_the_ocel_export_has_the_extension_of_the_imported_file(client, filename, extension):
    obj = _import(client, "ocel.tables", name="orders-log", filename=filename)

    [exporter] = data_of(client.get(f"/api/v3/objects/{obj['id']}/exporters"))
    assert (exporter["id"], exporter["label"]) == ("ocel.json", "OCEL 2.0 JSON")
    response = client.get(f"/api/v3/objects/{obj['id']}/export/ocel.json")

    assert response.status_code == 200
    assert response.mimetype == "application/json"
    assert f"filename=orders-log{extension}" in response.headers["Content-Disposition"]
    exported, original = json.loads(response.data), json.loads(DATA)
    assert exported["eventTypes"] == original["eventTypes"]
    assert [event["id"] for event in exported["events"]] == ["e1", "e2", "e3", "e4", "e5"]
    assert exported["events"][0]["relationships"] == original["events"][0]["relationships"]
    assert exported["objects"][0] == original["objects"][0]
    # A null attribute of the file stays null (e4's resource, i3's weight).
    assert exported["events"] == original["events"]
    assert exported["events"][3]["attributes"] == [{"name": "resource", "value": None}]
    assert exported["objects"][4]["attributes"][0]["value"] is None
    # Imported again, the export is the same log.
    again = _import(client, "ocel.tables", name="again", filename=filename, content=response.data)
    assert client.get(f"/api/v3/objects/{again['id']}/export/ocel.json").data == response.data


def test_deleting_the_tables_removes_their_folder(setup):
    client, _engine, _db, volume = setup
    obj = _import(client, "ocel.tables")
    assert (volume / "ocel" / obj["id"]).is_dir()

    assert client.delete(f"/api/v3/objects/{obj['id']}").status_code == 200

    assert not (volume / "ocel" / obj["id"]).exists()


# ---------------------------------------------------------------------- #
# As an EKG
# ---------------------------------------------------------------------- #
def _entity_types(volume, dataset):
    lines = (volume / dataset / f"{dataset}_entity.csv").read_text(encoding="utf-8").splitlines()
    assert lines[0] == "value,type"
    return sorted({line.split(",")[1] for line in lines[1:]})


def test_import_as_ekg_has_an_entity_type_per_object_type_and_the_ekg_views(setup):
    client, _engine, db, volume = setup

    obj = _import(client, "ocel.ekg")

    assert obj["kind"] == "ekg"
    meta = obj["meta"]
    assert meta["dataset"] == "orders"
    assert meta["mapping"] == {
        "event_id": "ocel:eid", "timestamp": "ocel:timestamp", "activity": "ocel:activity",
        "entities": ["customer", "item", "order"], "values": ["resource", "amount"],
    }
    assert meta["source_format"] == "ocel2_json"
    assert meta["ocel"]["not_in_graph"] == ["qualifiers", "object_objects"]
    assert meta["ocel"]["qualified_event_objects"] == 8
    assert "qualifier" in meta["notice"] and "oggetto-oggetto (4)" in meta["notice"]
    assert _entity_types(volume, "orders") == ["customer", "item", "order"]
    events = (volume / "orders" / "orders.csv").read_text(encoding="utf-8").splitlines()
    assert events[0] == "event_id,timestamp,activity_name,resource,amount,customer,item,order"
    # The ekg package normalizes the values (spaces become "_").
    assert events[1] == "e1,2023-01-01T09:00:00.000,place_order,Alice,,c1,\"i1,i2\",o1"
    assert any(query.text.startswith("LOAD CSV FROM") for query in db.received_queries)

    assert set(EKG_VISUALIZERS) <= set(_visualizers(client, obj["id"]))
    assert not {"ocel.tables", "ocel.summary"} & set(_visualizers(client, obj["id"]))


def test_decompose_into_ekg_creates_a_child_of_the_tables_with_the_same_graph(setup):
    client, _engine, _db, volume = setup
    tables = _import(client, "ocel.tables", filename="orders.jsonocel")
    direct = _import(client, "ocel.ekg", name="direct")

    response = client.post("/api/v3/operations/ocel.to_ekg/run", json={"objects": [tables["id"]], "params": {}})

    assert response.status_code == 201, response.get_json()
    [child] = data_of(response)
    assert (child["kind"], child["name"], child["parents"]) == ("ekg", "orders (EKG)", [tables["id"]])
    assert child["created_by"]["contributor_id"] == "ocel.to_ekg"
    assert child["meta"]["ocel"]["extension"] == ".jsonocel"
    assert child["meta"]["mapping"] == direct["meta"]["mapping"]
    dataset = child["meta"]["dataset"]
    for suffix in (".csv", "_entity.csv"):
        assert (volume / dataset / f"{dataset}{suffix}").read_bytes() == (volume / "direct" / f"direct{suffix}").read_bytes()
    assert set(EKG_VISUALIZERS) <= set(_visualizers(client, child["id"]))
    assert data_of(client.get(f"/api/v3/objects/{child['id']}"))["parents"] == [tables["id"]]


# ---------------------------------------------------------------------- #
# Installed at runtime from a zip
# ---------------------------------------------------------------------- #
def _ocel_zip() -> bytes:
    """The zip of `npm run pack -- ocel`: manifest, server/ and app/dist/ (a stand-in bundle if not built)."""

    root = BUNDLED_PACKAGES_DIR / "ocel"
    entries = {"soup-package.json": (root / "soup-package.json").read_bytes()}
    for path in sorted((root / "server").rglob("*.py")):
        entries[path.relative_to(root).as_posix()] = path.read_bytes()
    bundle = root / "app" / "dist" / "index.js"
    entries["app/dist/index.js"] = bundle.read_bytes() if bundle.is_file() else (
        b"customElements.define('soup-pkg-ocel-tables', class extends HTMLElement {});\n"
        b"customElements.define('soup-pkg-ocel-summary', class extends HTMLElement {});\n"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(f"ocel/{name}", content)
    return buffer.getvalue()


@pytest.fixture
def server_without_ocel(tmp_path, monkeypatch):
    """A server with the packages ocel requires (in code, from soup-packages) and nothing named ocel."""

    monkeypatch.setenv("SOUP_STORAGE_KIND", "local")
    monkeypatch.setenv("SOUP_LOCAL_STORAGE_ROOT", str(tmp_path / "volume"))
    bundled, installed = tmp_path / "bundled", tmp_path / "installed"
    bundled.mkdir()
    saved = {name: module for name, module in sys.modules.items() if name.startswith("soup_pkg_ocel")}
    settings = Settings(
        packages_path=(str(bundled), str(installed)), installed_packages_dir=str(installed), allow_package_install=True,
    )
    engine = build_engine(settings, extra_plugins=[bundled_plugin(name) for name in REQUIRED])
    use_database(engine, FakeDatabase())
    try:
        yield client_for(engine), engine
    finally:
        # The installed copy is imported as soup_pkg_ocel too: give the other tests back theirs.
        for name in [name for name in sys.modules if name.startswith("soup_pkg_ocel")]:
            del sys.modules[name]
        sys.modules.update(saved)


def test_installed_from_a_zip_its_contributions_are_available_at_once(server_without_ocel):
    client, engine = server_without_ocel
    assert engine.report.failed == [], engine.report.failed
    assert "ocel" not in [item["name"] for item in data_of(client.get("/api/v3/packages"))]
    assert data_of(client.get("/api/v3/importers", query_string={"filename": "orders.json"})) == []

    response = client.post(
        "/api/v3/packages", data={"file": (io.BytesIO(_ocel_zip()), "ocel-1.0.0.zip")}, content_type="multipart/form-data",
    )

    assert response.status_code == 201, response.get_json()
    info = data_of(response)
    assert (info["status"], info["origin"]) == ("active", "installed")
    assert info["contributions"] == {
        "importers": ["ocel.tables", "ocel.ekg"],
        "operations": ["ocel.to_ekg"],
        "visualizers": ["ocel.tables", "ocel.summary"],
        "exporters": ["ocel.json"],
        "tools": [],
    }
    importers = data_of(client.get("/api/v3/importers", query_string={"filename": "orders.json"}))
    assert sorted(item["id"] for item in importers) == ["ocel.ekg", "ocel.tables"]

    obj = _import(client, "ocel.tables")
    visualizers = data_of(client.get(f"/api/v3/objects/{obj['id']}/visualizers"))
    assert sorted((item["id"], item["element"], item["module_url"]) for item in visualizers) == [
        ("ocel.summary", "soup-pkg-ocel-summary", "/api/v3/packages/ocel/app/index.js"),
        ("ocel.tables", "soup-pkg-ocel-tables", "/api/v3/packages/ocel/app/index.js"),
    ]
    assert [item["id"] for item in data_of(client.get(f"/api/v3/objects/{obj['id']}/exporters"))] == ["ocel.json"]
    operations = data_of(client.get("/api/v3/operations", query_string={"objects": obj["id"]}))
    assert [item["id"] for item in operations] == ["ocel.to_ekg"]
    manifest = data_of(client.get("/api/v3/frontend/manifest"))
    assert any(item["name"] == "ocel" and item["module_url"] == "/api/v3/packages/ocel/app/index.js" for item in manifest)
    bundle = client.get("/api/v3/packages/ocel/app/index.js")
    assert bundle.status_code == 200 and b"soup-pkg-ocel-tables" in bundle.data


@pytest.mark.parametrize("filename, extension", [("orders.json", ".json"), ("orders.jsonocel", ".jsonocel")])
def test_the_list_of_exporters_shows_the_extension_of_the_imported_file(client, filename, extension):
    obj = _import(client, "ocel.tables", name="orders-log", filename=filename)

    [exporter] = data_of(client.get(f"/api/v3/objects/{obj['id']}/exporters"))

    assert (exporter["label"], exporter["extension"], exporter["mime"]) == ("OCEL 2.0 JSON", extension, "application/json")
