"""
------------------------------------------------------------------------
File : extract_legacy_routes.py
Description: Statically extracts the list of legacy Flask routes (method +
             full path) from app.py and the Controllers/ blueprints, using
             the `ast` module only (no import of the application code, no
             running Flask app, no database/Docker connection required).

             Writes the result to tests/fixtures/legacy_routes.json as a
             fixed baseline of the routes exposed today, so the behaviour
             of the API v2 surface can be checked for regressions while
             the "Pilastro 1 - Import" refactor is implemented.

             Run from the soup-server/ directory:
                 python tests/tools/extract_legacy_routes.py
Project : soup-server
------------------------------------------------------------------------
"""

import ast
import json
from pathlib import Path

SERVER_ROOT = Path(__file__).resolve().parent.parent.parent
CONTROLLERS_DIR = SERVER_ROOT / "Controllers"
APP_FILE = SERVER_ROOT / "app.py"
OUTPUT_FILE = SERVER_ROOT / "tests" / "fixtures" / "legacy_routes.json"

DEFAULT_METHODS = ["GET"]


def _literal(node):
    """Best-effort extraction of a literal value from an AST node."""

    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError):
        return None


def _blueprint_var_names(tree: ast.Module) -> set:
    """Return the set of variable names assigned to `Blueprint(...)` calls."""

    names = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not (isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name)
                and node.value.func.id == "Blueprint"):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                names.add(target.id)
    return names


def _route_decorator_info(decorator: ast.Call, known_bp_vars: set, allow_app: bool):
    """
    If `decorator` is a call to `<blueprint>.route(...)` (or `app.route(...)`
    when allow_app is True), return (path, methods). Otherwise return None.
    """

    func = decorator.func
    if not isinstance(func, ast.Attribute) or func.attr != "route":
        return None
    if not isinstance(func.value, ast.Name):
        return None

    owner = func.value.id
    if owner not in known_bp_vars and not (allow_app and owner == "app"):
        return None

    if not decorator.args:
        return None

    path = _literal(decorator.args[0])
    if not isinstance(path, str):
        return None

    methods = DEFAULT_METHODS
    for kw in decorator.keywords:
        if kw.arg == "methods":
            value = _literal(kw.value)
            if isinstance(value, (list, tuple)) and value:
                methods = list(value)

    return path, methods


def _extract_routes_from_file(file_path: Path, allow_app: bool = False):
    source = file_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(file_path))
    bp_vars = _blueprint_var_names(tree)

    routes = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            info = _route_decorator_info(decorator, bp_vars, allow_app=allow_app)
            if info is None:
                continue
            path, methods = info
            for method in methods:
                routes.append({
                    "method": method.upper(),
                    "path": path,
                    "source_file": file_path.relative_to(SERVER_ROOT).as_posix(),
                    "handler": node.name,
                })
    return routes


def extract_all_routes():
    routes = []

    if APP_FILE.exists():
        routes.extend(_extract_routes_from_file(APP_FILE, allow_app=True))

    if CONTROLLERS_DIR.exists():
        for file_path in sorted(CONTROLLERS_DIR.rglob("*.py")):
            routes.extend(_extract_routes_from_file(file_path, allow_app=False))

    routes.sort(key=lambda r: (r["path"], r["method"]))
    return routes


def main():
    routes = extract_all_routes()
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(routes, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Extracted {len(routes)} routes -> {OUTPUT_FILE.relative_to(SERVER_ROOT).as_posix()}")


if __name__ == "__main__":
    main()
