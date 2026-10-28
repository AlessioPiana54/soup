"""
------------------------------------------------------------------------
File : test_ekg_analysis_operations.py
Description: The analyses as operations, on the real host with the
             bundled packages, a FakeDatabase and the local storage on
             tmp_path: "Nuova analisi" creates an "ekg" object derived
             from its input (parents, meta.state, meta.graph_key, the file
             in the legacy format in <dataset>/Analyses/) that the
             visualizers of ekg_views open without rebuilding, and that is
             rebuilt by its provider (same key) after another graph was
             opened; an analysis that changes nothing is created as
             "unchanged" (file kept, notice shown); a failing filter
             creates nothing, removes the file and rebuilds the parent; a
             taken name is a 409; a legacy configuration is imported and
             run again; a filter of another package is a variant of "Nuova
             analisi"; the example configuration; the exporter of the
             configuration only for the analyses; deleting an analysis
             removes its file; the analyses on the volume become derived
             objects once.
Project : soup-packages/ekg_analysis
------------------------------------------------------------------------
"""

from __future__ import annotations

import base64
import json
import textwrap

import pytest

from soup.core.contracts import ConflictError, NotFoundError, ServiceUnavailableError, Upload, ValidationError
from tests.fakes import EKG_PACKAGES, FakeDatabase, ekg_engine
from tests.packages import bundled_module

filters = bundled_module("ekg_analysis", "filters")
operations = bundled_module("ekg_analysis", "operations")

PACKAGES = (*EKG_PACKAGES, "ekg_analysis")
CSV = b"case,activity,time,order\n1,Create,2021-01-01T10:00:00.000,o1\n2,Ship,2021-01-01T11:00:00.000,o1\n"
OPTIONS = {"event_id": "case", "timestamp": "time", "activity": "activity", "entities": ["order"]}

COUNT_NODES = "MATCH (n) RETURN count(n) AS count"
EXCLUDE_SHIP = {"variant": "excludeActivities", "values": {"activities": ["Ship"]}}
# The variant filter deletes nothing on the fake graph.
VARIANT = {"variant": "variant", "values": {"entity": "order", "operator": "=", "variant": 1}}


class GraphDatabase(FakeDatabase):
    """
    A FakeDatabase with a graph of `nodes` nodes, one less after each
    excluded activity, with the entity types and activities of CSV; it
    fails on the queries containing `fail_on`.
    """

    def __init__(self) -> None:
        super().__init__()
        self.nodes = 10
        self.fail_on: str | None = None
        self.set_response(filters.entity_types_query().text, [{"entity_type": "order"}])
        self.set_response(filters.activities_query().text, [{"activity": "Create"}, {"activity": "Ship"}])

    def run(self, query):
        if self.fail_on and self.fail_on in query.text:
            self.received_queries.append(query)
            raise RuntimeError("Memgraph failed")
        if query.text == COUNT_NODES:
            self.received_queries.append(query)
            return [{"count": self.nodes}]
        if "{ActivityName: $activity}" in query.text:
            self.nodes -= 1
        return super().run(query)

    def texts(self, start: int = 0) -> list[str]:
        return [query.text for query in self.received_queries[start:]]


def _engine(tmp_path, monkeypatch, packages=PACKAGES, db=None):
    db = db or GraphDatabase()
    engine = ekg_engine(tmp_path, monkeypatch, packages=packages, db=db)
    assert engine.report.failed == [], engine.report.failed
    return engine, db


@pytest.fixture
def setup(tmp_path, monkeypatch):
    engine, db = _engine(tmp_path, monkeypatch)
    root = engine.import_router.import_("csv_ekg.csv", Upload.from_bytes("orders.csv", CSV), "orders", options=OPTIONS)
    return engine, db, root


def _new(engine, root, name="a1", items=(EXCLUDE_SHIP,), **extra):
    [obj] = engine.operation_router.run("ekg_analysis.new", [root.id], {"name": name, "filters": list(items), **extra})
    return obj


def _state(engine):
    return engine.ctx.tool_registry.get("memgraph").current_state()


def _file(tmp_path, name="a1", dataset="orders"):
    return tmp_path / "volume" / dataset / "Analyses" / f"{name}.json"


def _rebuilt(db, start) -> bool:
    return any(text.startswith("LOAD CSV") for text in db.texts(start))


def test_a_new_analysis_is_an_ekg_object_derived_from_its_input(setup, tmp_path):
    engine, db, root = setup

    obj = _new(engine, root, description="Senza spedizioni")

    assert (obj.kind, obj.parents, obj.name, obj.description) == ("ekg", (root.id,), "a1", "Senza spedizioni")
    assert (obj.created_by.contributor_id, obj.created_by.package) == ("ekg_analysis.new", "ekg_analysis")
    assert obj.meta["state"] == {"provider": "analysis", "spec": {
        "name": "a1", "description": "Senza spedizioni", "filters": {"excludeActivities": [{"activities": ["Ship"]}]}}}
    assert obj.meta["analysis"] == {"dataset": "orders", "name": "a1"}
    assert obj.meta["counts"] == {"before": {"nodes": 10, "relationships": 0}, "after": {"nodes": 9, "relationships": 0}}
    assert (obj.meta["result"], "notice" in obj.meta) == ("changed", False)
    # The analysis is the loaded graph, under its own key.
    assert _state(engine) == obj.meta["graph_key"] != root.meta["graph_key"]

    saved = json.loads(_file(tmp_path).read_text(encoding="utf-8"))
    assert saved == {"timestamp": [], "performance": [], "includeActivities": [], "excludeActivities": [{"activities": ["Ship"]}],
                     "frequence": [], "variant": [], "dataset_name": "orders", "analysis_name": "a1",
                     "analysis_description": "Senza spedizioni"}


def test_the_visualizers_of_ekg_views_open_it_without_rebuilding(setup):
    engine, db, root = setup
    obj = _new(engine, root)
    start = len(db.received_queries)

    assert [entry.key for entry in engine.visualizer_router.visualizers_for(obj.id)] == [
        "ekg_views.graph", "ekg_analysis.insights", "ekg_views.queries", "ekg_views.stats"]
    graph = engine.visualizer_router.data("ekg_views.graph", obj.id, {})
    stats = engine.visualizer_router.data("ekg_views.stats", obj.id, {})
    queries = engine.visualizer_router.data("ekg_views.queries", obj.id, {})

    assert graph["view"] == "standard" and stats["counts"]["event_nodes"] == 0 and queries["groups"]
    assert (graph["notice"], stats["notice"], queries["notice"]) == (None, None, None)
    assert not _rebuilt(db, start)


def test_after_another_graph_its_provider_rebuilds_it_with_the_same_key(setup):
    engine, db, root = setup
    obj = _new(engine, root)
    engine.visualizer_router.data("ekg_views.stats", root.id, {})
    assert _state(engine) == root.meta["graph_key"]

    start = len(db.received_queries)
    engine.visualizer_router.data("ekg_views.stats", obj.id, {})

    texts = db.texts(start)
    load = next(index for index, text in enumerate(texts) if text.startswith("LOAD CSV"))
    replayed = [index for index, query in enumerate(db.received_queries[start:]) if query.params.get("activity") == "Ship"]
    assert replayed and load < replayed[0]
    # No counts and no "analysis.before_apply" on a rebuild.
    assert COUNT_NODES not in texts
    assert _state(engine) == obj.meta["graph_key"]


def test_analysis_that_changes_nothing_is_rolled_back(setup, tmp_path):
    engine, db, root = setup

    obj = _new(engine, root, name="same", items=(VARIANT,))

    assert obj.meta["result"] == "unchanged"
    assert obj.meta["counts"]["before"] == obj.meta["counts"]["after"]
    assert obj.meta["notice"] == operations.UNCHANGED_NOTICE
    # The file is kept, like the legacy "Nothing changed".
    assert json.loads(_file(tmp_path, "same").read_text(encoding="utf-8"))["variant"] == [VARIANT["values"]]
    assert _state(engine) == obj.meta["graph_key"]
    for visualizer in ("ekg_views.graph", "ekg_views.stats", "ekg_views.queries"):
        assert engine.visualizer_router.data(visualizer, obj.id, {})["notice"] == operations.UNCHANGED_NOTICE


def test_a_failing_filter_creates_nothing_removes_the_file_and_rebuilds_the_parent(setup, tmp_path):
    engine, db, root = setup
    db.fail_on = "WHERE event_count"
    before = [item.id for item in engine.core_tools.catalog().list()]
    start = len(db.received_queries)

    with pytest.raises(RuntimeError, match="Memgraph failed"):
        _new(engine, root, items=(EXCLUDE_SHIP, VARIANT))

    assert [item.id for item in engine.core_tools.catalog().list()] == before
    assert not _file(tmp_path).exists()
    texts = db.texts(start)
    failed = next(index for index, text in enumerate(texts) if "WHERE event_count" in text)
    assert any(text.startswith("LOAD CSV") for text in texts[failed:])
    assert _state(engine) == root.meta["graph_key"]


def test_a_taken_name_is_a_409_and_does_not_touch_the_graph(setup, tmp_path):
    engine, db, root = setup
    _new(engine, root)
    start = len(db.received_queries)

    with pytest.raises(ConflictError, match="a1"):
        _new(engine, root, items=(VARIANT,))

    assert not any("WHERE event_count" in text for text in db.texts(start))
    assert json.loads(_file(tmp_path).read_text(encoding="utf-8"))["variant"] == []


def _upload(content, name="old.json") -> dict:
    raw = content if isinstance(content, bytes) else json.dumps(content).encode("utf-8")
    return {"filename": name, "base64": base64.b64encode(raw).decode("ascii")}


LEGACY = {
    "timestamp": [], "performance": [], "includeActivities": [],
    "excludeActivities": [{"activities": ["Ship"]}], "frequence": [],
    "variant": [{"entity": "order", "operator": "!=", "variant": 3}],
    "dataset_name": "another", "analysis_name": "whatever", "analysis_description": "Dal vecchio formato",
}


def test_an_analysis_in_the_legacy_format_is_imported_and_run_again(setup, tmp_path):
    engine, db, root = setup
    start = len(db.received_queries)

    [obj] = engine.operation_router.run("ekg_analysis.import", [root.id], {"name": "old", "file": _upload(LEGACY)})

    assert obj.description == "Dal vecchio formato"
    assert obj.meta["state"]["spec"]["filters"] == {"excludeActivities": [{"activities": ["Ship"]}],
                                                    "variant": [{"entity": "order", "operator": "!=", "variant": 3}]}
    variant = next(query for query in db.received_queries[start:] if "WHERE event_count" in query.text)
    assert "event_count <> $variant" in variant.text and variant.params == {"entity": "order", "variant": 3}
    saved = json.loads(_file(tmp_path, "old").read_text(encoding="utf-8"))
    assert (saved["dataset_name"], saved["analysis_name"]) == ("orders", "old")

    # Run again after another graph: rebuilt, both filters replayed in order.
    engine.visualizer_router.data("ekg_views.stats", root.id, {})
    start = len(db.received_queries)
    engine.visualizer_router.data("ekg_views.stats", obj.id, {})
    applied = [query.params.get("activity") or query.params.get("variant") for query in db.received_queries[start:]
               if "activity" in query.params or "variant" in query.params]
    assert applied == ["Ship", 3]
    assert _state(engine) == obj.meta["graph_key"]


@pytest.mark.parametrize("content, message", [
    (b"{not json", "not valid JSON"),
    ({"performance": [{"entity": "order", "operator": "~", "seconds": 1}]}, r"performance\[0\]: operator"),
    ({"magic": [{"x": 1}]}, "magic: unknown filter"),
])
def test_an_invalid_configuration_is_refused_filter_by_filter(setup, tmp_path, content, message):
    engine, _db, root = setup
    with pytest.raises(ValidationError, match=message):
        engine.operation_router.run("ekg_analysis.import", [root.id], {"name": "bad", "file": _upload(content)})
    assert not _file(tmp_path, "bad").exists()


TEST_MANIFEST = {
    "name": "filter_test",
    "version": "1.0.0",
    "api_version": "4.0",
    "requires": ["ekg_analysis"],
    "requires_tools": [],
    "server": {"module": "server", "plugin": "plugin:Plugin"},
}

TEST_PLUGIN = '''
from soup.core.contracts import Field, PluginContext, SoupPlugin
from soup_pkg_ekg.api import Query, ident
from soup_pkg_ekg_analysis.api import ANALYSIS_FILTERS_POINT, AnalysisFilter


class OnlyLongEvents(AnalysisFilter):
    key = "test.only_long"
    label = "Solo eventi lunghi"
    description = "Un filtro di prova."
    order = 700

    def fields(self, obj, tools):
        return [Field("minutes", "Minuti", type="number", required=True)]

    def validate(self, spec):
        return {"minutes": int(spec["minutes"])}

    def to_queries(self, spec, ctx):
        return [Query(f"MATCH (e:{ident('Event')}) WHERE e.minutes < $minutes DETACH DELETE e", {"minutes": spec["minutes"]})]


class Plugin(SoupPlugin):
    def register(self, ctx: PluginContext) -> None:
        item = OnlyLongEvents()
        ctx.contribute(ANALYSIS_FILTERS_POINT, item, key=item.key, order=item.order)
'''


def test_a_filter_of_another_package_is_a_variant_of_new_analysis(tmp_path, monkeypatch):
    folder = tmp_path / "installed" / "filter_test"
    (folder / "server").mkdir(parents=True)
    (folder / "soup-package.json").write_text(json.dumps(TEST_MANIFEST), encoding="utf-8")
    (folder / "server" / "__init__.py").write_text("", encoding="utf-8")
    (folder / "server" / "plugin.py").write_text(textwrap.dedent(TEST_PLUGIN), encoding="utf-8")
    engine, db = _engine(tmp_path, monkeypatch, packages=(*PACKAGES, "filter_test"))
    root = engine.import_router.import_("csv_ekg.csv", Upload.from_bytes("orders.csv", CSV), "orders", options=OPTIONS)

    [_name, _description, items] = engine.operation_router.fields("ekg_analysis.new", [root.id])
    assert [variant.key for variant in items.variants] == [*filters.LEGACY_FILTER_KEYS, "test.only_long"]
    assert [spec.name for spec in items.variant("test.only_long").fields] == ["minutes"]

    start = len(db.received_queries)
    obj = _new(engine, root, items=({"variant": "test.only_long", "values": {"minutes": 5}}, EXCLUDE_SHIP))
    texts = db.texts(start)
    # After the six filters of ekg_analysis (order 700).
    assert texts.index("MATCH (e:`Event`) WHERE e.minutes < $minutes DETACH DELETE e") > next(
        index for index, text in enumerate(texts) if "{ActivityName: $activity}" in text)
    assert obj.meta["state"]["spec"]["filters"]["test.only_long"] == [{"minutes": 5}]

    engine.package_manager.disable("filter_test")
    [_name, _description, items] = engine.operation_router.fields("ekg_analysis.new", [root.id])
    assert "test.only_long" not in [variant.key for variant in items.variants]
    engine.visualizer_router.data("ekg_views.stats", root.id, {})
    with pytest.raises(ServiceUnavailableError, match="test.only_long"):
        engine.visualizer_router.data("ekg_views.stats", obj.id, {})


def test_the_example_configuration_is_a_report_built_on_the_object(setup):
    engine, db, root = setup
    db.set_response(filters.time_range_query().text, [{"first": "2021-01-01T10:00:00", "last": "2021-01-01T11:00:00"}])

    [report] = engine.operation_router.run("ekg_analysis.example", [root.id], {})

    assert (report.kind, report.parents) == ("report", (root.id,))
    markdown, file = report.meta["blocks"]
    assert markdown["type"] == "markdown"
    for key in filters.LEGACY_FILTER_KEYS:
        assert f"`{key}`" in markdown["data"]["markdown"]
    assert (file["type"], file["data"]["filename"]) == ("file", "analysis_example.json")
    example = json.loads(base64.b64decode(file["data"]["base64"]))
    assert example["timestamp"] == [{"startDate": "2021-01-01T10:00:00", "endDate": "2021-01-01T11:00:00"}]
    assert example["performance"][0]["entity"] == "order"
    assert example["includeActivities"] == [{"activities": ["Create"]}]
    assert example["excludeActivities"] == [{"activities": ["Ship"]}]
    # It can be imported as it is.
    [obj] = engine.operation_router.run("ekg_analysis.import", [root.id], {"name": "from_example", "file": _upload(example)})
    assert set(obj.meta["state"]["spec"]["filters"]) == set(filters.LEGACY_FILTER_KEYS)


def test_the_configuration_exporter_applies_only_to_analyses(setup, tmp_path):
    engine, _db, root = setup
    obj = _new(engine, root)

    assert "ekg_analysis.config" in [entry.key for entry in engine.export_router.exporters_for(obj.id)]
    assert "ekg_analysis.config" not in [entry.key for entry in engine.export_router.exporters_for(root.id)]
    exported = engine.export_router.export("ekg_analysis.config", obj.id)
    assert (exported.filename, exported.mime) == ("a1.json", "application/json")
    assert json.loads(exported.content) == json.loads(_file(tmp_path).read_text(encoding="utf-8"))
    with pytest.raises(NotFoundError):
        engine.export_router.export("ekg_analysis.config", root.id)


def test_deleting_an_analysis_removes_its_file_and_its_graph(setup, tmp_path):
    engine, _db, root = setup
    obj = _new(engine, root)
    assert _state(engine) == obj.meta["graph_key"]

    engine.workspace_service.delete(obj.id)

    assert not _file(tmp_path).exists()
    assert _state(engine) is None
    assert engine.core_tools.catalog().get(root.id) is not None


def test_the_analyses_on_the_volume_become_derived_objects_once(tmp_path, monkeypatch):
    engine, _db = _engine(tmp_path, monkeypatch)
    root = engine.import_router.import_("csv_ekg.csv", Upload.from_bytes("orders.csv", CSV), "orders", options=OPTIONS)
    analyses = tmp_path / "volume" / "orders" / "Analyses"
    analyses.mkdir(parents=True, exist_ok=True)
    (analyses / "legacy.json").write_text(json.dumps({**LEGACY, "other.filter": [{"x": 1}]}), encoding="utf-8")
    (analyses / "broken.json").write_text("{not json", encoding="utf-8")
    (analyses / "_hidden.json").write_text("{}", encoding="utf-8")

    restarted, _db = _engine(tmp_path, monkeypatch)

    [adopted] = [obj for obj in restarted.core_tools.catalog().list() if obj.parents == (root.id,)]
    assert (adopted.name, adopted.kind, adopted.description) == ("legacy", "ekg", "Dal vecchio formato")
    assert (adopted.created_by.type, adopted.created_by.contributor_id) == ("operation", "ekg_analysis.new")
    assert adopted.meta["analysis"] == {"dataset": "orders", "name": "legacy"}
    assert "graph_key" not in adopted.meta
    # A filter of a package not loaded yet is kept as it is.
    assert adopted.meta["state"]["spec"]["filters"]["other.filter"] == [{"x": 1}]

    again, _db = _engine(tmp_path, monkeypatch)
    assert len([obj for obj in again.core_tools.catalog().list() if obj.parents == (root.id,)]) == 1


# ---------------------------------------------------------------------- #
# Nested analyses
# ---------------------------------------------------------------------- #
def _nested(engine, root):
    first = _new(engine, root, name="first", items=(EXCLUDE_SHIP,))
    [second] = engine.operation_router.run("ekg_analysis.new", [first.id], {"name": "second", "filters": [VARIANT]})
    return first, second


def test_a_nested_analysis_names_its_parent_in_its_file(setup, tmp_path):
    engine, _db, root = setup
    first, second = _nested(engine, root)

    assert second.parents == (first.id,)
    assert second.meta["analysis"] == {"dataset": "orders", "name": "second", "based_on": "first"}
    assert json.loads(_file(tmp_path, "second").read_text(encoding="utf-8"))["based_on"] == "first"
    assert "based_on" not in json.loads(_file(tmp_path, "first").read_text(encoding="utf-8"))
    assert json.loads(engine.export_router.export("ekg_analysis.config", second.id).content)["based_on"] == "first"


def test_deleting_an_analysis_with_children_follows_the_workspace_rule(setup, tmp_path):
    engine, _db, root = setup
    first, second = _nested(engine, root)

    with pytest.raises(ConflictError, match="derived"):
        engine.workspace_service.delete(first.id)
    assert _file(tmp_path, "first").exists()

    assert engine.workspace_service.delete(first.id, cascade=True) == [second.id, first.id]
    assert not _file(tmp_path, "first").exists() and not _file(tmp_path, "second").exists()


def test_a_chain_lost_from_the_catalog_is_adopted_again_with_the_filters_of_both(tmp_path, monkeypatch):
    engine, _db = _engine(tmp_path, monkeypatch)
    root = engine.import_router.import_("csv_ekg.csv", Upload.from_bytes("orders.csv", CSV), "orders", options=OPTIONS)
    first, second = _nested(engine, root)
    catalog = engine.core_tools.catalog()
    catalog.remove(second.id)
    catalog.remove(first.id)

    restarted, db = _engine(tmp_path, monkeypatch)

    adopted = {obj.name: obj for obj in restarted.core_tools.catalog().list() if obj.name in ("first", "second")}
    assert adopted["first"].parents == (root.id,)
    assert adopted["second"].parents == (adopted["first"].id,)
    assert adopted["second"].meta["analysis"]["based_on"] == "first"
    assert "warning" not in adopted["second"].meta

    start = len(db.received_queries)
    restarted.visualizer_router.data("ekg_views.stats", adopted["second"].id, {})
    applied = [query.params.get("activity") or query.params.get("variant") for query in db.received_queries[start:]
               if "activity" in query.params or "variant" in query.params]
    assert applied == ["Ship", 1]


def _write_analysis(tmp_path, name, content):
    folder = tmp_path / "volume" / "orders" / "Analyses"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.json").write_text(json.dumps(content), encoding="utf-8")


def test_a_based_on_that_does_not_exist_or_a_cycle_is_adopted_under_the_root_with_a_warning(tmp_path, monkeypatch, caplog):
    engine, _db = _engine(tmp_path, monkeypatch)
    root = engine.import_router.import_("csv_ekg.csv", Upload.from_bytes("orders.csv", CSV), "orders", options=OPTIONS)
    exclude = {"excludeActivities": [{"activities": ["Ship"]}]}
    _write_analysis(tmp_path, "orphan", {**exclude, "based_on": "gone"})
    _write_analysis(tmp_path, "ping", {**exclude, "based_on": "pong"})
    _write_analysis(tmp_path, "pong", {**exclude, "based_on": "ping"})

    with caplog.at_level("WARNING", logger="soup.ekg_analysis"):
        restarted, _db = _engine(tmp_path, monkeypatch)

    adopted = {obj.name: obj for obj in restarted.core_tools.catalog().list() if obj.name in ("orphan", "ping", "pong")}
    assert set(adopted) == {"orphan", "ping", "pong"}
    for obj in adopted.values():
        assert obj.parents == (root.id,)
        assert obj.meta["warning"] == obj.meta["notice"]
        assert "based_on" not in obj.meta["analysis"]
    assert "'gone'" in adopted["orphan"].meta["warning"]
    assert "cycle" in adopted["ping"].meta["warning"]
    logged = " ".join(record.getMessage() for record in caplog.records)
    assert "orphan" in logged and "ping" in logged and "pong" in logged
