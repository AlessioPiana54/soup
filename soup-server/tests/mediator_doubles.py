"""
------------------------------------------------------------------------
File : mediator_doubles.py
Description: Configurable fake importers, operations, visualizers,
             exporters, tools and packages for the tests of the core
             mediator. Wired only through public contracts, like a real
             package.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional, Sequence

from soup.core.contracts import (
    Exporter,
    Field,
    Importer,
    Inspection,
    ObjectDraft,
    ObjectRef,
    Operation,
    OperationInput,
    PluginContext,
    SoupPlugin,
    Tool,
    ToolAccess,
    Upload,
    Visualizer,
)
from soup.core.contracts import report
from soup.core.engine import build_engine
from soup.core.settings import Settings
from tests.fakes import CoreToolsPackage, FakeDatabase, InMemoryFileStorage


class FakeImporter(Importer):
    def __init__(
        self,
        importer_id: str,
        label: str,
        extensions: Sequence[str] = (".csv",),
        produces: str = "table",
        requires_tools: Sequence[str] = (),
        fail_with: Optional[Exception] = None,
        meta: Any = None,
    ):
        self.id = importer_id
        self.label = label
        self.extensions = tuple(extensions)
        self.produces = produces
        self.requires_tools = tuple(requires_tools)
        self.fail_with = fail_with
        self.meta = {"rows": 2} if meta is None else meta
        self.calls: list[tuple[str, Any]] = []
        self.disposed: list[str] = []

    def inspect(self, upload: Upload, tools: ToolAccess) -> Inspection:
        self.calls.append(("inspect", upload.filename))
        return Inspection(
            preview=[report.text(f"{self.id}:{upload.read().decode('utf-8')}")],
            fields=[Field("separator", type="text", default=",")],
        )

    def preview(self, upload: Upload, options: Mapping[str, Any], tools: ToolAccess) -> list[dict[str, Any]]:
        self.calls.append(("preview", dict(options)))
        return [report.text(f"{self.id} separator={options.get('separator')}")]

    def import_(self, upload: Upload, obj: ObjectRef, options: Mapping[str, Any], tools: ToolAccess) -> Any:
        self.calls.append(("import", obj))
        if self.fail_with is not None:
            raise self.fail_with
        return self.meta

    def dispose(self, obj: ObjectRef, tools: ToolAccess) -> None:
        self.disposed.append(obj.id)


class FakeOperation(Operation):
    """
    `inputs` is a list of (name, kinds) pairs. By default run() returns
    one object per kind in `produces`, named "<op id> of <first input name>".
    """

    def __init__(
        self,
        operation_id: str,
        inputs: Sequence[tuple[str, Sequence[str]]],
        produces: Sequence[str] = ("table",),
        label: str = "",
        group: str = "Filters",
        requires_tools: Sequence[str] = (),
        fields: Optional[Callable[[Mapping[str, ObjectRef]], list[Field]]] = None,
        result: Optional[Callable[[Mapping[str, ObjectRef], Mapping[str, Any]], list[Any]]] = None,
    ):
        self.id = operation_id
        self.label = label or operation_id
        self.group = group
        self.inputs = tuple(OperationInput(name, tuple(kinds)) for name, kinds in inputs)
        self.produces = tuple(produces)
        self.requires_tools = tuple(requires_tools)
        self._fields = fields
        self._result = result
        self.runs: list[tuple[dict[str, str], dict[str, Any]]] = []
        self.disposed: list[str] = []

    def fields(self, inputs: Mapping[str, ObjectRef], tools: ToolAccess) -> list[Field]:
        return self._fields(inputs) if self._fields else []

    def run(self, inputs: Mapping[str, ObjectRef], params: Mapping[str, Any], tools: ToolAccess) -> list[ObjectDraft]:
        self.runs.append(({name: obj.id for name, obj in inputs.items()}, dict(params)))
        if self._result is not None:
            return self._result(inputs, params)
        first = next(iter(inputs.values()))
        return [ObjectDraft(f"{self.id} of {first.name}", kind, {"params": dict(params)}) for kind in self.produces]

    def dispose(self, obj: ObjectRef, tools: ToolAccess) -> None:
        self.disposed.append(obj.id)


class FakeVisualizer(Visualizer):
    def __init__(self, visualizer_id: str, accepts: Sequence[str], label: str = "", requires_tools: Sequence[str] = ()):
        self.id = visualizer_id
        self.label = label or visualizer_id
        self.accepts = accepts if isinstance(accepts, str) else tuple(accepts)
        self.element = f"soup-{visualizer_id.replace('_', '-')}"
        self.requires_tools = tuple(requires_tools)

    def data(self, obj: ObjectRef, params: Mapping[str, Any], tools: ToolAccess) -> Any:
        return {"visualizer": self.id, "object": obj.id, "params": dict(params)}

    def action(self, obj: ObjectRef, name: str, params: Mapping[str, Any], tools: ToolAccess) -> Any:
        if name == "search":
            return {"matches": [obj.name], "query": params.get("q")}
        return super().action(obj, name, params, tools)


class FakeExporter(Exporter):
    def __init__(self, exporter_id: str, accepts: Sequence[str], extension: str = ".csv", mime: str = "text/csv"):
        self.id = exporter_id
        self.label = exporter_id
        self.accepts = tuple(accepts)
        self.extension = extension
        self.mime = mime

    def fields(self, obj: ObjectRef, tools: ToolAccess) -> list[Field]:
        return [Field("separator", type="select", choices=(",", ";"), default=",")]

    def export(self, obj: ObjectRef, params: Mapping[str, Any], tools: ToolAccess) -> bytes:
        return f"{obj.name}{params['separator']}{obj.kind}".encode("utf-8")


class FakeTool(Tool):
    def __init__(self, name: str):
        self.name = name

    def health(self) -> dict[str, Any]:
        return {"ok": True}


class FeaturePackage(SoupPlugin):
    """A package contributing the given importers/operations/visualizers/exporters/tools."""

    def __init__(
        self,
        name: str,
        importers: Sequence[Importer] = (),
        operations: Sequence[Operation] = (),
        visualizers: Sequence[Visualizer] = (),
        exporters: Sequence[Exporter] = (),
        tools: Sequence[Tool] = (),
        requires: Sequence[str] = (),
        requires_tools: Sequence[str] = (),
        provides_tools: Optional[Sequence[str]] = None,
        extension_points: Sequence[str] = (),
        on_register: Optional[Callable[[PluginContext], None]] = None,
    ):
        self.name = name
        self.version = "1.0.0"
        self.requires = tuple(requires)
        self.requires_tools = tuple(requires_tools)
        self.provides_tools = tuple(provides_tools if provides_tools is not None else (t.name for t in tools))
        self.extension_points = tuple(extension_points)
        self._tools = list(tools)
        self._importers = list(importers)
        self._operations = list(operations)
        self._visualizers = list(visualizers)
        self._exporters = list(exporters)
        self._on_register = on_register

    def register(self, ctx: PluginContext) -> None:
        for tool in self._tools:
            ctx.add_tool(tool)
        for importer in self._importers:
            ctx.add_importer(importer)
        for operation in self._operations:
            ctx.add_operation(operation)
        for visualizer in self._visualizers:
            ctx.add_visualizer(visualizer)
        for exporter in self._exporters:
            ctx.add_exporter(exporter)
        if self._on_register is not None:
            self._on_register(ctx)


def build_test_engine(*packages: SoupPlugin, with_core_tools: bool = True):
    """An engine with no built-in plugins, the in-memory core tools and `packages`."""

    core = CoreToolsPackage()
    extra = [core, *packages] if with_core_tools else list(packages)
    engine = build_engine(
        Settings.from_env({"SOUP_PACKAGES": ""}),
        db=FakeDatabase(),
        storage=InMemoryFileStorage(),
        extra_plugins=extra,
    )
    return engine, core


def upload(name: str = "log.csv", content: bytes = b"a,b\n1,2\n") -> Upload:
    return Upload.from_bytes(name, content, "text/csv")


def published(engine, event: str) -> list[dict[str, Any]]:
    """Subscribe a recorder to `event` (as the core-tools test package) and return its list."""

    received: list[dict[str, Any]] = []
    engine.event_bus.subscribe(event, lambda payload: received.append(dict(payload)), owner="test_recorder")
    return received
