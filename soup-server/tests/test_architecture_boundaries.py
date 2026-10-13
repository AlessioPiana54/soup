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
