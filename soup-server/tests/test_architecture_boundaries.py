"""
------------------------------------------------------------------------
File : test_architecture_boundaries.py
Description: Static (AST-based) checks of the dependency rules: soup/core
             never imports from soup/api; the packages in soup-packages/
             never import Flask, reach the host only through
             soup.core.contracts and another package only through its
             api.py, after declaring it in `requires`; soup/core/contracts
             never imports pandas; soup/api is the only package that
             imports Flask; and nothing under soup/ imports the Memgraph
             driver or the Docker SDK any more (they belong to the
             tool_memgraph and tool_storage packages, commit 3); text
             and csv_table use the standard library and the "storage"
             tool only (no pandas, no Memgraph driver, commit 7); the
             whole of soup/core imports none of pandas, neo4j, docker and
             Flask, and the event log and the EKG are gone from it to the
             ekg, csv_ekg and causal_df packages (commit 8). The tests
             kept next to a package (soup-packages/<name>/tests) are not
             part of it (not packed) and are not checked.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

SOUP_ROOT = Path(__file__).resolve().parent.parent / "soup"
PACKAGES_ROOT = Path(__file__).resolve().parent.parent.parent / "soup-packages"


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


def _package_files(package_dir: Path) -> list[Path]:
    """The Python files of a package, without its tests/ folder."""

    return [path for path in _py_files(package_dir) if "tests" not in path.relative_to(package_dir).parts]


def test_core_never_imports_from_api_or_packages():
    violations = []
    for file_path in _py_files(SOUP_ROOT / "core"):
        for module in _imported_modules(file_path):
            if module.startswith("soup.api") or module.startswith("soup_pkg_"):
                violations.append(f"{file_path.relative_to(SOUP_ROOT)} imports {module}")
    assert violations == []


def test_soup_plugins_is_gone():
    # The built-in plugins moved to soup-packages/ (commit 2).
    assert not (SOUP_ROOT / "plugins").exists()


def test_contracts_never_import_pandas():
    violations = []
    for file_path in _py_files(SOUP_ROOT / "core" / "contracts"):
        for module in _imported_modules(file_path):
            if _is_pandas_module(module):
                violations.append(f"{file_path.relative_to(SOUP_ROOT)} imports {module}")
    assert violations == []


def _package_dirs() -> list[Path]:
    return sorted(path.parent for path in PACKAGES_ROOT.glob("*/soup-package.json"))


def test_bundled_packages_exist():
    assert {path.name for path in _package_dirs()} >= {
        "ekg", "csv_ekg", "causal_df", "tool_memgraph", "tool_storage", "soup_base", "text", "csv_table",
    }
    assert not (PACKAGES_ROOT / "csv_reader").exists()


def test_soup_infrastructure_is_gone():
    # The adapters moved to soup-packages/tool_memgraph and tool_storage (commit 3).
    assert not (SOUP_ROOT / "infrastructure").exists()


def test_host_never_imports_the_database_driver_or_docker():
    violations = []
    for file_path in _py_files(SOUP_ROOT):
        for module in _imported_modules(file_path):
            if module.split(".")[0] in ("neo4j", "docker"):
                violations.append(f"{file_path.relative_to(SOUP_ROOT)} imports {module}")
    assert violations == []


def test_tool_packages_have_no_app_part():
    for name in ("tool_memgraph", "tool_storage"):
        manifest = json.loads((PACKAGES_ROOT / name / "soup-package.json").read_text(encoding="utf-8"))
        assert "app" not in manifest
        assert not (PACKAGES_ROOT / name / "app").exists()


STDLIB_PACKAGES = ("text", "csv_table")


def test_text_and_csv_table_import_neither_pandas_nor_the_database_driver():
    violations = []
    for name in STDLIB_PACKAGES:
        for file_path in _package_files(PACKAGES_ROOT / name):
            for module in _imported_modules(file_path):
                if module.split(".")[0] in ("pandas", "neo4j", "docker") or module.startswith("soup_pkg_tool_memgraph"):
                    violations.append(f"{file_path.relative_to(PACKAGES_ROOT)} imports {module}")
    assert violations == []


def test_text_and_csv_table_only_need_the_storage_tool():
    for name in STDLIB_PACKAGES:
        manifest = json.loads((PACKAGES_ROOT / name / "soup-package.json").read_text(encoding="utf-8"))
        assert manifest["requires"] == ["soup_base", "tool_storage"]
        assert manifest["requires_tools"] == ["storage"]
        assert manifest["python_dependencies"] == []


def test_packages_never_import_flask():
    violations = []
    for package_dir in _package_dirs():
        for file_path in _package_files(package_dir):
            for module in _imported_modules(file_path):
                if _is_flask_module(module):
                    violations.append(f"{file_path.relative_to(PACKAGES_ROOT)} imports {module}")
    assert violations == []


def test_packages_reach_the_host_only_through_contracts_and_others_only_through_api():
    violations = []
    for package_dir in _package_dirs():
        manifest = json.loads((package_dir / "soup-package.json").read_text(encoding="utf-8"))
        allowed_packages = {f"soup_pkg_{name}.api" for name in manifest.get("requires", [])}
        for file_path in _package_files(package_dir):
            relative = file_path.relative_to(PACKAGES_ROOT)
            for module in _imported_modules(file_path):
                if module == "soup" or (module.startswith("soup.") and not module.startswith("soup.core.contracts")):
                    violations.append(f"{relative} imports host module {module}")
                if module.startswith("soup_pkg_") and module not in allowed_packages:
                    violations.append(f"{relative} imports {module} (not api.py of a package in requires)")
    assert violations == []


# The mediator: contracts, package wiring and routing services. None of it
# may depend on a data library, a database driver, Docker or Flask.
MEDIATOR_PATHS = (
    "core/contracts",
    "core/packages",
    "core/settings.py",
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
    "core/services/orphaned_data.py",
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
            if root in _FORBIDDEN_IN_MEDIATOR or root.startswith("flask_"):
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


def test_the_whole_core_imports_no_data_library_database_docker_or_flask():
    violations = []
    for file_path in _py_files(SOUP_ROOT / "core"):
        for module in _imported_modules(file_path):
            root = module.split(".")[0]
            if root in _FORBIDDEN_IN_MEDIATOR or root.startswith("flask_"):
                violations.append(f"{file_path.relative_to(SOUP_ROOT)} imports {module}")
    assert violations == []


# What commit 8 moved to the ekg, csv_ekg and causal_df packages.
MOVED_FROM_THE_CORE = (
    "core/event_log.py",
    "core/dataset_repository.py",
    "core/tables.py",
    "core/process_timer.py",
    "core/ekg",
    "core/services/event_log_handler.py",
    "core/services/ekg_service.py",
    "core/services/import_service.py",
    "core/services/legacy_tools.py",
    "core/contracts/event_log.py",
    "core/contracts/input.py",
    "core/contracts/build.py",
    "core/contracts/tables.py",
)


def test_the_event_log_and_the_ekg_are_gone_from_the_core():
    assert [path for path in MOVED_FROM_THE_CORE if (SOUP_ROOT / path).exists()] == []
    # Nor does the core mention them: no Cypher of the EKG, no event-log names
    # (but in the version history of the contracts, which records the removal).
    violations = []
    for file_path in _py_files(SOUP_ROOT / "core"):
        if file_path == SOUP_ROOT / "core" / "contracts" / "version.py":
            continue
        text = file_path.read_text(encoding="utf-8")
        for word in ("EventLog", "ColumnMapping", "EkgBuildStep", "LOAD CSV", ":CORR", "add_build_step", "add_input_reader"):
            if word in text:
                violations.append(f"{file_path.relative_to(SOUP_ROOT)} mentions {word}")
    assert violations == []


def test_ekg_packages_declare_what_they_use():
    manifests = {
        name: json.loads((PACKAGES_ROOT / name / "soup-package.json").read_text(encoding="utf-8"))
        for name in ("ekg", "csv_ekg", "causal_df")
    }
    assert manifests["ekg"]["requires"] == ["tool_memgraph", "tool_storage"]
    assert set(manifests["ekg"]["requires_tools"]) >= {"memgraph", "storage"}
    assert manifests["ekg"]["extension_points"] == ["ekg.build_steps", "ekg.state_providers"]
    assert "app" not in manifests["ekg"]
    assert manifests["csv_ekg"]["requires"] == ["ekg", "soup_base", "csv_table"]
    assert manifests["causal_df"]["requires"] == ["ekg"]
