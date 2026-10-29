"""
------------------------------------------------------------------------
File : test_visualizer_export_router.py
Description: Tests for VisualizerRouter and ExportRouter - contributions
             offered per object kind, an empty list for a kind nobody
             accepts, data/action/export routed to the chosen one;
             Exporter.applies (contracts "3.1") narrows an exporter to
             some objects: not listed and a 404 on a direct export when
             False, excluded and logged (never a 500) when it raises;
             Exporter.file_type (contracts "4.1") gives the extension and
             the MIME type of each file, the exporter's own by default,
             and an invalid one is a 500 naming the package, never a
             file name; the list of exporters shows the file type of each
             object (default params), the fixed one with a warning when
             file_type() fails.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import logging

import pytest

from soup.core.contracts import DomainError, NotFoundError, ValidationError
from tests.api_client import client_for, data_of
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


# ---------------------------------------------------------------------- #
# Exporter.file_type (contracts "4.1")
# ---------------------------------------------------------------------- #
class PerObject(FakeExporter):
    """The extension and the MIME type come from the object's meta, or are `given`."""

    def __init__(self, exporter_id: str, given=None):
        super().__init__(exporter_id, ["text"], ".txt", "text/plain")
        self.given = given
        self.calls = []

    def file_type(self, obj, params):
        self.calls.append((obj.name, dict(params)))
        if self.given is not None:
            return self.given
        return obj.meta.get("extension", self.extension), obj.meta.get("mime", self.mime)


def _file_type_setup(*exporters):
    importers = [
        FakeImporter("md", "Markdown", produces="text", meta={"extension": ".md", "mime": "text/markdown"}),
        FakeImporter("log", "Log", produces="text", meta={"extension": ".log"}),
        FakeImporter("plain", "Plain", produces="text"),
    ]
    engine, _core = build_test_engine(FeaturePackage("files", importers=importers, exporters=list(exporters)))
    objects = {key: engine.import_router.import_(f"files.{key}", upload(), f"notes-{key}") for key in ("md", "log", "plain")}
    return engine, objects


def test_an_exporter_that_does_not_redefine_file_type_keeps_its_extension_and_mime():
    exporter = FakeExporter("csv", ["text"])
    engine, objects = _file_type_setup(exporter)

    assert exporter.file_type(objects["md"], {}) == (".csv", "text/csv")
    exported = engine.export_router.export("files.csv", objects["md"].id, {"separator": ";"})
    assert (exported.filename, exported.mime) == ("notes-md.csv", "text/csv")


def test_file_type_names_each_file_with_its_own_extension_and_mime():
    exporter = PerObject("original")
    engine, objects = _file_type_setup(exporter)

    files = {key: engine.export_router.export("files.original", obj.id) for key, obj in objects.items()}

    assert {key: (item.filename, item.mime) for key, item in files.items()} == {
        "md": ("notes-md.md", "text/markdown"),
        "log": ("notes-log.log", "text/plain"),
        "plain": ("notes-plain.txt", "text/plain"),
    }
    # It receives the validated params, defaults included.
    assert exporter.calls[0] == ("notes-md", {"separator": ","})


@pytest.mark.parametrize("given", [
    ("md", "text/plain"),                       # no leading dot
    (".", "text/plain"),                        # too short
    ("." + "x" * 16, "text/plain"),             # too long (17 characters)
    ("./../x", "text/plain"),                   # path separators
    (".md\\x", "text/plain"),
    (".m d", "text/plain"),
    (".md\n", "text/plain"),
    (".md", "markdown"),                        # no subtype
    (".md", "text/plain; charset=utf-8"),       # parameters are not part of the type
    (".md", "text/plain\r\nX-Evil: 1"),
    (".md", None),
    (None, "text/plain"),
    (".md",),
    "text/plain",
])
def test_an_invalid_file_type_is_a_500_naming_the_package_and_builds_no_file_name(given, caplog):
    engine, objects = _file_type_setup(PerObject("bad", given=given))

    with caplog.at_level(logging.ERROR, logger="soup.export"), pytest.raises(DomainError) as exc_info:
        engine.export_router.export("files.bad", objects["md"].id)

    assert exc_info.value.http_status_code == 500
    assert "'files.bad'" in str(exc_info.value) and "package 'files'" in str(exc_info.value)
    assert any("files.bad" in record.getMessage() and "'files'" in record.getMessage() for record in caplog.records)


def test_valid_extensions_at_the_limits_are_accepted():
    for extension in (".x", ".tar.gz", ".jsonocel", "." + "a" * 15, ".my-file_v2"):
        engine, objects = _file_type_setup(PerObject("ok", given=(extension, "application/vnd.ocel+json")))
        assert engine.export_router.export("files.ok", objects["md"].id).filename == f"notes-md{extension}"


def test_over_http_an_invalid_file_type_answers_500_with_the_message_and_no_file():
    engine, objects = _file_type_setup(PerObject("bad", given=("../x", "text/plain")))

    response = client_for(engine).get(f"/api/v3/objects/{objects['md'].id}/export/files.bad")

    assert response.status_code == 500
    message = response.get_json()["message"]
    assert "files.bad" in message and "package 'files'" in message
    assert "Content-Disposition" not in response.headers


# ---------------------------------------------------------------------- #
# The list of exporters shows the file type of the object
# ---------------------------------------------------------------------- #
class Raising(FakeExporter):
    def __init__(self, exporter_id: str):
        super().__init__(exporter_id, ["text"], ".txt", "text/plain")

    def file_type(self, obj, params):
        raise RuntimeError("file_type exploded")


def test_the_list_shows_the_file_type_of_each_object_with_the_default_params():
    exporter = PerObject("original")
    engine, objects = _file_type_setup(exporter)
    client = client_for(engine)

    listed = {
        key: data_of(client.get(f"/api/v3/objects/{obj.id}/exporters"))[0] for key, obj in objects.items()
    }

    assert {key: (item["extension"], item["mime"]) for key, item in listed.items()} == {
        "md": (".md", "text/markdown"), "log": (".log", "text/plain"), "plain": (".txt", "text/plain"),
    }
    # file_type() received the defaults of the fields (FakeExporter: separator ",").
    assert exporter.calls[0][1] == {"separator": ","}


@pytest.mark.parametrize("broken", [Raising("broken"), PerObject("broken", given=("../x", "text/plain"))])
def test_a_failing_file_type_lists_the_fixed_extension_with_a_warning_and_no_500(broken, caplog):
    engine, objects = _file_type_setup(broken)
    client = client_for(engine)

    with caplog.at_level(logging.WARNING, logger="soup.export"):
        response = client.get(f"/api/v3/objects/{objects['md'].id}/exporters")

    assert response.status_code == 200
    [item] = data_of(response)
    assert (item["id"], item["extension"], item["mime"]) == ("files.broken", ".txt", "text/plain")
    assert any(
        record.levelno == logging.WARNING and "files.broken" in record.getMessage() and "'files'" in record.getMessage()
        for record in caplog.records
    )
    # The export itself still refuses it.
    assert client.get(f"/api/v3/objects/{objects['md'].id}/export/files.broken").status_code == 500
