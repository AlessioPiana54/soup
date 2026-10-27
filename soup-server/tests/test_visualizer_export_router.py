"""
------------------------------------------------------------------------
File : test_visualizer_export_router.py
Description: Tests for VisualizerRouter and ExportRouter - contributions
             offered per object kind, an empty list for a kind nobody
             accepts, data/action/export routed to the chosen one;
             Exporter.applies (contracts "3.1") narrows an exporter to
             some objects: not listed and a 404 on a direct export when
             False, excluded and logged (never a 500) when it raises.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import logging

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


class OnlyNamed(FakeExporter):
    """Applies only to the objects called `name`."""

    def __init__(self, exporter_id: str, name: str):
        super().__init__(exporter_id, ["table"])
        self.name = name
        self.seen_tools = []

    def applies(self, obj, tools) -> bool:
        self.seen_tools.append(tools)
        return obj.name == self.name


class Broken(FakeExporter):
    def applies(self, obj, tools) -> bool:
        raise RuntimeError("applies exploded")


def _applies_setup():
    exporters = [FakeExporter("csv", ["table"]), OnlyNamed("orders_only", "orders"), Broken("broken", ["table"])]
    package = FeaturePackage("tables", importers=[FakeImporter("tab", "Table", produces="table")], exporters=exporters)
    engine, _core = build_test_engine(package)
    orders = engine.import_router.import_("tables.tab", upload(), "orders")
    items = engine.import_router.import_("tables.tab", upload(), "items")
    return engine, orders, items, exporters


def test_an_exporter_without_applies_is_offered_for_every_object_of_its_kinds():
    assert FakeExporter("csv", ["table"]).applies(None, None) is True


def test_an_exporter_that_does_not_apply_is_not_listed_and_its_direct_export_is_a_404(caplog):
    engine, orders, items, exporters = _applies_setup()

    with caplog.at_level(logging.ERROR, logger="soup.export"):
        assert [e.key for e in engine.export_router.exporters_for(orders.id)] == ["tables.csv", "tables.orders_only"]
        assert [e.key for e in engine.export_router.exporters_for(items.id)] == ["tables.csv"]

    assert engine.export_router.export("tables.orders_only", orders.id, {"separator": ","}).content == b"orders,table"
    assert exporters[1].seen_tools[-1] is not None
    with pytest.raises(NotFoundError, match="orders_only"):
        engine.export_router.export("tables.orders_only", items.id, {"separator": ","})
    with pytest.raises(NotFoundError):
        engine.export_router.fields("tables.orders_only", items.id)


def test_an_applies_that_raises_excludes_the_exporter_and_is_logged(caplog):
    engine, orders, _items, _exporters = _applies_setup()

    with caplog.at_level(logging.ERROR, logger="soup.export"):
        keys = [e.key for e in engine.export_router.exporters_for(orders.id)]
    assert "tables.broken" not in keys
    assert any("tables.broken" in record.getMessage() and "'tables'" in record.getMessage() for record in caplog.records)
    with pytest.raises(NotFoundError):
        engine.export_router.export("tables.broken", orders.id, {"separator": ","})
