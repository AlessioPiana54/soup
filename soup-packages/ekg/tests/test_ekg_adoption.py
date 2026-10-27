"""
------------------------------------------------------------------------
File : test_ekg_adoption.py
Description: The datasets already on the volume (/soup/<name>/ with a
             <name>_config.json, written by the old pages) become "ekg"
             objects of the catalog when the ekg package starts, created
             by the csv_ekg importer, with the meta read from the config;
             a second start adds nothing; folders without a config, with
             a broken config or already in the catalog are skipped. The
             adopted object loads and is deleted like an imported one.
Project : soup-packages/ekg
------------------------------------------------------------------------
"""

from __future__ import annotations

import json

from tests.fakes import FakeDatabase, ekg_engine, volume_files

LEGACY_CONFIG = {
    "dataset_name": "legacy",
    "dataset_description": "From the old pages",
    "all_columns": ["EventID", "Activity", "Timestamp", "Items"],
    "standard_columns": ["event_id", "timestamp", "activity_name"],
    "filtered_columns": ["Items"],
    "values_columns": [],
    "trigger_target_rows": [],
    "event_nodes": 2,
    "entity_nodes": 3,
    "corr_rel": 3,
    "df_rel": 1,
    "date_created": "2024-05-01T10:00:00.000",
    "date_modified": "2024-05-01T10:00:01.000",
    "process_info": {"init_time": "2024-05-01T10:00:00.000", "finish_time": "2024-05-01T10:00:01.000"},
    "svg_content": None,
}


def _write(tmp_path, path: str, content: bytes) -> None:
    target = tmp_path / "volume" / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)


def _legacy_volume(tmp_path) -> None:
    _write(tmp_path, "legacy/legacy.csv", b"event_id,timestamp,activity_name,Items\ne1,2021-01-01T10:00:00.000,Create,i1\n")
    _write(tmp_path, "legacy/legacy_entity.csv", b"value,type\ni1,Items\n")
    _write(tmp_path, "legacy/legacy_config.json", json.dumps(LEGACY_CONFIG).encode("utf-8"))
    _write(tmp_path, "legacy/Analyses/a1.json", b"{}")
    _write(tmp_path, "no_config/no_config.csv", b"x\n")
    _write(tmp_path, "broken/broken_config.json", b"{not json")


def _ekg_objects(engine):
    return [obj for obj in engine.core_tools.catalog().list() if obj.kind == "ekg"]


def test_the_datasets_on_the_volume_become_ekg_objects(tmp_path, monkeypatch):
    _legacy_volume(tmp_path)

    engine = ekg_engine(tmp_path, monkeypatch)

    [obj] = _ekg_objects(engine)
    assert (obj.name, obj.description, obj.created_at, obj.parents) == (
        "legacy", "From the old pages", "2024-05-01T10:00:00.000", (),
    )
    assert (obj.created_by.type, obj.created_by.contributor_id, obj.created_by.package) == ("importer", "csv_ekg.csv", "csv_ekg")
    assert obj.meta["dataset"] == "legacy"
    assert isinstance(obj.meta["graph_key"], str) and obj.meta["graph_key"] != obj.id
    assert obj.meta["columns"] == LEGACY_CONFIG["all_columns"]
    assert obj.meta["mapping"] == {
        "event_id": "event_id", "timestamp": "timestamp", "activity": "activity_name", "entities": ["Items"], "values": [],
    }
    assert obj.meta["counts"] == {"event_nodes": 2, "entity_nodes": 3, "corr_rel": 3, "df_rel": 1}
    assert obj.meta["process_info"]["init_time"] == "2024-05-01T10:00:00.000"
    assert obj.meta["process_info"]["init_df_time"] is None
    # The importer that created it is the one that disposes of it.
    assert engine.import_router.get("csv_ekg.csv") is not None


def test_a_second_start_adds_nothing(tmp_path, monkeypatch):
    _legacy_volume(tmp_path)
    ekg_engine(tmp_path, monkeypatch).shutdown()

    engine = ekg_engine(tmp_path, monkeypatch)

    assert [obj.name for obj in _ekg_objects(engine)] == ["legacy"]


def test_an_imported_dataset_is_not_adopted_again(tmp_path, monkeypatch):
    from soup.core.contracts import Upload

    engine = ekg_engine(tmp_path, monkeypatch)
    engine.import_router.import_(
        "csv_ekg.csv",
        Upload.from_bytes("o.csv", b"id,act,ts\n1,A,2021-01-01T10:00:00.000\n"),
        "orders",
        options={"event_id": "id", "activity": "act", "timestamp": "ts"},
    )
    engine.shutdown()

    engine = ekg_engine(tmp_path, monkeypatch)

    assert [obj.meta["dataset"] for obj in _ekg_objects(engine)] == ["orders"]


def test_an_adopted_dataset_loads_and_deletes_like_an_imported_one(tmp_path, monkeypatch):
    _legacy_volume(tmp_path)
    db = FakeDatabase()
    engine = ekg_engine(tmp_path, monkeypatch, db=db)
    [obj] = _ekg_objects(engine)

    engine.operation_router.run("ekg.load", [obj.id])
    assert engine.ctx.tool_registry.get("memgraph").current_state() == obj.meta["graph_key"]

    load = [query.text for query in db.received_queries if query.text.startswith("LOAD CSV")]
    assert any("legacy/legacy.csv" in text for text in load)
    corr = [query.params for query in db.received_queries if "CORR" in query.text and "MERGE" in query.text]
    assert {"entity_type": "Items"} in corr

    engine.workspace_service.delete(obj.id)
    assert [path for path in volume_files(tmp_path) if path.startswith("legacy/")] == []
