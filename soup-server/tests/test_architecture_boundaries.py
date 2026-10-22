"""
------------------------------------------------------------------------
File : test_architecture_boundaries.py
Description: Static (AST-based) checks of the dependency rules: soup/core
             never imports from soup/plugins or soup/api; soup/plugins
             never imports Flask; soup/core/contracts never imports
             pandas; and soup/api is the only package that imports Flask.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import ast
from pathlib import Path

SOUP_ROOT = Path(__file__).resolve().parent.parent / "soup"


def _imported_modules(file_path: Path) -> set[str]:
    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _is_flask_module(name: str) -> bool:
    return name == "flask" or name.startswith("flask.") or name.startswith("flask_")


def _is_pandas_module(name: str) -> bool:
    return name == "pandas" or name.startswith("pandas.")


def _py_files(directory: Path) -> list[Path]:
    return sorted(directory.rglob("*.py")) if directory.exists() else []


def test_core_never_imports_from_plugins_or_api():
    violations = []
    for file_path in _py_files(SOUP_ROOT / "core"):
        for module in _imported_modules(file_path):
            if module.startswith("soup.plugins") or module.startswith("soup.api"):
                violations.append(f"{file_path.relative_to(SOUP_ROOT)} imports {module}")
    assert violations == []


def test_contracts_never_import_pandas():
    violations = []
    for file_path in _py_files(SOUP_ROOT / "core" / "contracts"):
        for module in _imported_modules(file_path):
            if _is_pandas_module(module):
                violations.append(f"{file_path.relative_to(SOUP_ROOT)} imports {module}")
    assert violations == []


def test_plugins_never_import_flask():
    violations = []
    for file_path in _py_files(SOUP_ROOT / "plugins"):
        for module in _imported_modules(file_path):
            if _is_flask_module(module):
                violations.append(f"{file_path.relative_to(SOUP_ROOT)} imports {module}")
    assert violations == []


# The mediator: contracts, package wiring and routing services. None of it
# may depend on a data library, a database driver, Docker or Flask.
# (soup/core/tables.py, event_log.py, ekg/ and the legacy import services
# leave the core in later commits.)
MEDIATOR_PATHS = (
    "core/contracts",
    "core/registry.py",
    "core/plugin_context.py",
    "core/plugin_manager.py",
    "core/events.py",
    "core/event_bus.py",
    "core/extension_points.py",
    "core/toolbox.py",
    "core/field_validation.py",
    "core/services/core_tools.py",
    "core/services/import_router.py",
    "core/services/operation_router.py",
    "core/services/visualizer_router.py",
    "core/services/export_router.py",
    "core/services/workspace_service.py",
)

_FORBIDDEN_IN_MEDIATOR = ("pandas", "neo4j", "docker", "flask", "werkzeug")


def _mediator_files() -> list[Path]:
    files: list[Path] = []
    for relative in MEDIATOR_PATHS:
        path = SOUP_ROOT / relative
        files.extend(_py_files(path) if path.is_dir() else [path])
    return files


def test_mediator_imports_no_data_library_database_docker_or_flask():
    violations = []
    for file_path in _mediator_files():
        assert file_path.exists(), file_path
        for module in _imported_modules(file_path):
            root = module.split(".")[0]
            if root in _FORBIDDEN_IN_MEDIATOR or root.startswith("flask_") or module.startswith("soup.infrastructure"):
                violations.append(f"{file_path.relative_to(SOUP_ROOT)} imports {module}")
    assert violations == []


def test_only_soup_api_imports_flask():
    violations = []
    for file_path in _py_files(SOUP_ROOT):
        relative = file_path.relative_to(SOUP_ROOT)
        if relative.parts[0] == "api":
            continue
        for module in _imported_modules(file_path):
            if _is_flask_module(module):
                violations.append(f"{relative} imports {module}")
    assert violations == []
