"""
------------------------------------------------------------------------
File : test_contributions_contract.py
Description: Liskov substitution for every contribution registered by
             the default packages (an engine with all the bundled
             packages, FakeDatabase as Memgraph, the local storage): each
             Importer, Operation, Visualizer, Exporter and Tool can stand
             where the core expects its base class.
             - the declared attributes have the shape the core relies on
               (ids, labels, kinds, extensions, element tags, tools among
               those of its package);
             - the required methods are implemented (no abstract method
               left, nothing raising NotImplementedError when called);
             - an overridden method keeps the parameters of the base, by
               name and order (the core calls them by position and by
               keyword), and adds only optional ones;
             - the documented outcomes: an unknown visualizer action is a
               NotFoundError, applies() a bool, file_type() a valid
               (extension, mime), Tool.health() a dict without raising.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import inspect
import re
import tempfile
from pathlib import Path

import pytest

from soup.core.contracts import (
    CreatedBy,
    Exporter,
    Field,
    Importer,
    NotFoundError,
    ObjectRef,
    Operation,
    Tool,
    Visualizer,
)
from soup.core.engine import build_engine
from soup.core.settings import Settings
from tests.fakes import FakeDatabase, use_database
from tests.packages import BUNDLED_PACKAGES_DIR

BASES = {"importers": Importer, "operations": Operation, "visualizers": Visualizer, "exporters": Exporter}
EXTENSION = re.compile(r"\.[A-Za-z0-9._-]{1,15}")
MIME = re.compile(r"[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]*/[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]*")


def _build_engine():
    """One engine with every bundled package, built when the module is collected (it gives the parameters)."""

    root = Path(tempfile.mkdtemp(prefix="soup-contract-"))
    installed = root / "installed"
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("SOUP_STORAGE_KIND", "local")
        patch.setenv("SOUP_LOCAL_STORAGE_ROOT", str(root / "volume"))
        settings = Settings(
            packages=None, packages_path=(str(BUNDLED_PACKAGES_DIR), str(installed)), installed_packages_dir=str(installed),
        )
        built = build_engine(settings)
    use_database(built, FakeDatabase())
    return built


ENGINE = _build_engine()


def _entries(kind):
    registry = {
        "importers": ENGINE.ctx.importers, "operations": ENGINE.ctx.operations,
        "visualizers": ENGINE.ctx.visualizers, "exporters": ENGINE.ctx.exporters,
    }[kind]
    return registry.entries()


CONTRIBUTIONS = [(kind, entry.key) for kind in BASES for entry in _entries(kind)]


@pytest.fixture(scope="module")
def engine():
    assert ENGINE.report.failed == [], ENGINE.report.failed
    yield ENGINE
    ENGINE.shutdown()


def _entry(engine, kind, key):
    return next(entry for entry in _entries(kind) if entry.key == key)


def _manifest_tools(engine, package):
    source = engine.package_manager.source(package)
    assert source is not None, package
    return set(source.manifest.requires_tools) | set(source.manifest.provides_tools)


def _dummy(kind: str) -> ObjectRef:
    return ObjectRef("contract-object", "contract", kind, CreatedBy("importer", "contract.importer", "contract"))


def test_the_default_packages_contribute_something_of_every_kind():
    kinds = {kind for kind, _key in CONTRIBUTIONS}
    assert kinds == set(BASES)
    assert len(CONTRIBUTIONS) > 30


@pytest.mark.parametrize(("kind", "key"), CONTRIBUTIONS)
def test_every_contribution_is_a_complete_subclass_of_its_base(engine, kind, key):
    entry = _entry(engine, kind, key)
    item = entry.item
    base = BASES[kind]

    assert isinstance(item, base)
    assert not inspect.isabstract(type(item)), f"{key} leaves abstract methods: {type(item).__abstractmethods__}"
    assert isinstance(item.id, str) and item.id and key == f"{entry.package}.{item.id}"
    assert set(item.requires_tools) <= _manifest_tools(engine, entry.package), key


@pytest.mark.parametrize(("kind", "key"), CONTRIBUTIONS)
def test_overridden_methods_keep_the_parameters_of_the_base(engine, kind, key):
    item = _entry(engine, kind, key).item
    base = BASES[kind]
    for name, base_method in inspect.getmembers(base, inspect.isfunction):
        if name.startswith("_"):
            continue
        method = getattr(type(item), name, None)
        if method is None or method is base_method or not inspect.isfunction(method):
            continue
        expected = list(inspect.signature(base_method).parameters.values())
        actual = list(inspect.signature(method).parameters.values())
        assert [p.name for p in actual[:len(expected)]] == [p.name for p in expected], f"{key}.{name}"
        extra = actual[len(expected):]
        assert all(p.default is not inspect.Parameter.empty or p.kind is p.VAR_KEYWORD for p in extra), f"{key}.{name}"


@pytest.mark.parametrize(("kind", "key"), [item for item in CONTRIBUTIONS if item[0] == "importers"])
def test_importers_declare_extensions_and_a_kind(engine, kind, key):
    importer = _entry(engine, kind, key).item

    assert isinstance(importer.label, str) and importer.label
    assert isinstance(importer.produces, str) and importer.produces
    assert importer.extensions and all(EXTENSION.fullmatch(extension) for extension in importer.extensions)
    assert all(importer.accepts(f"file{extension}") for extension in importer.extensions)


@pytest.mark.parametrize(("kind", "key"), [item for item in CONTRIBUTIONS if item[0] == "operations"])
def test_operations_declare_inputs_and_what_they_produce(engine, kind, key):
    operation = _entry(engine, kind, key).item

    assert isinstance(operation.label, str) and operation.label
    assert operation.inputs and all(slot.name and slot.kinds for slot in operation.inputs)
    assert operation.produces and all(isinstance(produced, str) and produced for produced in operation.produces)


@pytest.mark.parametrize(("kind", "key"), [item for item in CONTRIBUTIONS if item[0] == "visualizers"])
def test_an_unknown_visualizer_action_is_a_not_found(engine, kind, key):
    entry = _entry(engine, kind, key)
    visualizer = entry.item
    assert "-" in visualizer.element and visualizer.accepts
    tools = engine.core_tools.toolbox(f"visualizer '{key}'", visualizer.requires_tools)

    with pytest.raises(NotFoundError):
        visualizer.action(_dummy(tuple(visualizer.accepts)[0]), "no-such-action", {}, tools)


@pytest.mark.parametrize(("kind", "key"), [item for item in CONTRIBUTIONS if item[0] == "exporters"])
def test_exporters_declare_a_valid_file_type(engine, kind, key):
    entry = _entry(engine, kind, key)
    exporter = entry.item
    tools = engine.core_tools.toolbox(f"exporter '{key}'", exporter.requires_tools)
    obj = _dummy(tuple(exporter.accepts)[0])

    assert EXTENSION.fullmatch(exporter.extension) and MIME.fullmatch(exporter.mime), key
    assert isinstance(exporter.applies(obj, tools), bool)
    extension, mime = exporter.file_type(obj, {})
    assert EXTENSION.fullmatch(extension) and MIME.fullmatch(mime), key
    assert all(isinstance(field, Field) for field in exporter.fields(obj, tools) or [])


def test_every_tool_answers_its_health_with_a_dict(engine):
    tools = list(engine.ctx.tool_registry.entries())
    assert {entry.key for entry in tools} >= {"memgraph", "storage", "catalog", "preferences"}
    for entry in tools:
        assert isinstance(entry.item, Tool) and entry.item.name == entry.key
        health = entry.item.health()
        assert isinstance(health, dict), entry.key
