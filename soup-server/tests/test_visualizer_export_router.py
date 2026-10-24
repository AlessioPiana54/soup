"""
------------------------------------------------------------------------
File : test_visualizer_export_router.py
Description: Tests for VisualizerRouter and ExportRouter - contributions
             offered per object kind, an empty list for a kind nobody
             accepts, data/action/export routed to the chosen one.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import pytest

from soup.core.contracts import NotFoundError, ValidationError
from tests.mediator_doubles import (
    FakeExporter,
    FakeImporter,
    FakeVisualizer,
    FeaturePackage,
    build_test_engine,
    upload,
)


def _setup():
    importers = [
        FakeImporter("tab", "Table", produces="table"),
        FakeImporter("txt", "Text", extensions=(".txt",), produces="text"),
    ]
    graph_package = FeaturePackage(
        "graph_views",
        visualizers=[FakeVisualizer("dfg", ["event_log", "table"], label="Directly-follows")],
    )
    table_package = FeaturePackage(
        "tables",
        importers=importers,
        visualizers=[FakeVisualizer("grid", "table", label="Grid")],
        exporters=[FakeExporter("csv", ["table"]), FakeExporter("json", ["table", "event_log"], ".json", "application/json")],
    )
    engine, _core = build_test_engine(graph_package, table_package)
    table = engine.import_router.import_("tables.tab", upload(), "orders")
    text = engine.import_router.import_("tables.txt", upload("n.txt"), "notes")
    return engine, table, text


def test_visualizers_are_filtered_by_kind_and_a_kind_without_any_gets_an_empty_list():
    engine, table, text = _setup()

    assert [v.key for v in engine.visualizer_router.visualizers_for(table.id)] == ["graph_views.dfg", "tables.grid"]
    assert engine.visualizer_router.visualizers_for(text.id) == []
    assert engine.visualizer_router.package_of("tables.grid") == "tables"
    assert engine.visualizer_router.package_of("graph_views.dfg") == "graph_views"


def test_visualizer_data_and_action_are_routed():
    engine, table, text = _setup()

    assert engine.visualizer_router.data("tables.grid", table.id, {"page": 2}) == {
        "visualizer": "grid", "object": table.id, "params": {"page": 2}
    }
    assert engine.visualizer_router.action("tables.grid", table.id, "search", {"q": "ord"}) == {
        "matches": ["orders"], "query": "ord"
    }
    with pytest.raises(NotFoundError, match="no action 'explode'"):
        engine.visualizer_router.action("tables.grid", table.id, "explode")
    with pytest.raises(ValidationError):
        engine.visualizer_router.action("tables.grid", table.id, "")
    with pytest.raises(NotFoundError):
        engine.visualizer_router.data("tables.grid", text.id)
    with pytest.raises(NotFoundError):
        engine.visualizer_router.data("tables.missing", table.id)


def test_exporters_are_filtered_by_kind():
    engine, table, text = _setup()

    assert [e.key for e in engine.export_router.exporters_for(table.id)] == ["tables.csv", "tables.json"]
    assert engine.export_router.exporters_for(text.id) == []
    assert [f.name for f in engine.export_router.fields("tables.csv", table.id)] == ["separator"]


def test_export_validates_options_and_names_the_file_after_the_object():
    engine, table, text = _setup()

    exported = engine.export_router.export("tables.csv", table.id, {"separator": ";"})

    assert (exported.filename, exported.mime, exported.content) == ("orders.csv", "text/csv", b"orders;table")
    assert engine.export_router.export("tables.json", table.id).content == b"orders,table"
    with pytest.raises(ValidationError):
        engine.export_router.export("tables.csv", table.id, {"separator": "|"})
    with pytest.raises(NotFoundError):
        engine.export_router.export("tables.csv", text.id)
