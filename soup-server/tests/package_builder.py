"""
------------------------------------------------------------------------
File : package_builder.py
Description: Writes throw-away packages (soup-package.json + server/) on
             disk and packs them into zips, for the tests of the
             PackageManager. The generated plugin registers an input
             reader keyed by a constant of its own helper module (so two
             packages with the same file names prove their imports are
             isolated), adds every tool its manifest provides and opens
             every extension point it declares. Other templates register
             an importer "csv", or something they did not declare.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import io
import json
import uuid
import zipfile
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from soup.core.contracts import CONTRACTS_API_VERSION

DEFAULT_PLUGIN = '''
from soup.core.contracts import PluginContext, SoupPlugin, Tool

from .helper import MARKER


class _Tool(Tool):
    def __init__(self, name):
        self.name = name

    def health(self):
        return {"ok": True}


class Plugin(SoupPlugin):
    def register(self, ctx: PluginContext) -> None:
        ctx.add_input_reader(MARKER, object())
        for tool in self.provides_tools:
            ctx.add_tool(_Tool(tool))
        for point in self.extension_points:
            ctx.add_extension_point(point)
'''

# Registers an importer with the local id "csv" (every package using this
# template has one: the full keys "<package>.csv" keep them apart).
IMPORTER_PLUGIN = '''
from soup.core.contracts import Importer, Inspection, PluginContext, SoupPlugin


class CsvImporter(Importer):
    id = "csv"
    extensions = (".csv",)
    produces = "table"

    def __init__(self, label):
        self.label = label

    def inspect(self, upload, tools):
        return Inspection()

    def import_(self, upload, obj, options, tools):
        return {}

    def dispose(self, obj, tools):
        pass


class Plugin(SoupPlugin):
    def register(self, ctx: PluginContext) -> None:
        ctx.add_importer(CsvImporter(self.name))
'''

UNDECLARED_TOOL_PLUGIN = '''
from soup.core.contracts import SoupPlugin, Tool


class _Tool(Tool):
    name = "secret"

    def health(self):
        return {"ok": True}


class Plugin(SoupPlugin):
    def register(self, ctx):
        ctx.add_tool(_Tool())
'''

UNDECLARED_POINT_PLUGIN = '''
from soup.core.contracts import SoupPlugin


class Plugin(SoupPlugin):
    def register(self, ctx):
        ctx.add_extension_point("hidden")
'''

FAILING_PLUGIN = '''
from soup.core.contracts import SoupPlugin


class Plugin(SoupPlugin):
    def register(self, ctx):
        raise RuntimeError("register failed on purpose")
'''

# A server module that must never be imported (python_dependencies or
# api_version checks have to exclude the package first).
EXPLODING_INIT = 'raise RuntimeError("this package must not be imported")\n'


def manifest_for(
    name: str,
    version: str = "1.0.0",
    requires: Sequence[str] = (),
    requires_tools: Sequence[str] = (),
    provides_tools: Sequence[str] = (),
    extension_points: Sequence[str] = (),
    python_dependencies: Sequence[str] = (),
    api_version: str = CONTRACTS_API_VERSION,
) -> dict[str, Any]:
    return {
        "name": name,
        "version": version,
        "api_version": api_version,
        "label": name.title(),
        "description": f"Test package {name}",
        "author": "tests",
        "requires": list(requires),
        "requires_tools": list(requires_tools),
        "provides_tools": list(provides_tools),
        "extension_points": list(extension_points),
        "python_dependencies": list(python_dependencies),
        "server": {"module": "server", "plugin": "plugin:Plugin"},
    }


def write_package(
    root: Path,
    name: str,
    *,
    plugin_source: str = DEFAULT_PLUGIN,
    init_source: str = "",
    marker: Optional[str] = None,
    manifest: Optional[Mapping[str, Any]] = None,
    **manifest_fields: Any,
) -> Path:
    """Write <root>/<name>/ and return its folder."""

    package_dir = Path(root) / name
    server = package_dir / "server"
    server.mkdir(parents=True)
    data = dict(manifest) if manifest is not None else manifest_for(name, **manifest_fields)
    (package_dir / "soup-package.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    (server / "__init__.py").write_text(init_source, encoding="utf-8")
    (server / "helper.py").write_text(f"MARKER = {(marker or name)!r}\n", encoding="utf-8")
    (server / "plugin.py").write_text(plugin_source, encoding="utf-8")
    (server / "api.py").write_text("from .helper import MARKER\n", encoding="utf-8")
    return package_dir


def zip_folder(package_dir: Path, top_folder: bool = True) -> bytes:
    """Zip a package folder, inside a top-level folder named after it or at the root."""

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(Path(package_dir).rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                relative = path.relative_to(package_dir).as_posix()
                archive.write(path, f"{Path(package_dir).name}/{relative}" if top_folder else relative)
    return buffer.getvalue()


def build_zip(tmp_path: Path, name: str, **kwargs: Any) -> bytes:
    """Write a package in a scratch folder and return it zipped."""

    scratch = tmp_path / "zip-sources" / uuid.uuid4().hex
    scratch.mkdir(parents=True)
    return zip_folder(write_package(scratch, name, **kwargs))


def zip_entries(entries: Mapping[str, bytes], symlinks: Sequence[str] = ()) -> bytes:
    """A zip with exactly these entries (names unchecked) plus symbolic links."""

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in entries.items():
            archive.writestr(zipfile.ZipInfo(name), content)
        for name in symlinks:
            info = zipfile.ZipInfo(name)
            info.external_attr = (0o120777 << 16)
            archive.writestr(info, "/etc/passwd")
    return buffer.getvalue()
