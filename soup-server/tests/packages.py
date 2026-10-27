"""
------------------------------------------------------------------------
File : packages.py
Description: Access to the packages shipped in soup-packages/ from the
             tests, through the same isolated import the PackageManager
             uses (soup_pkg_<name>). Tests reach a package through its
             public api.py, like another package would; the tests kept
             next to a package (soup-packages/<name>/tests) may also
             reach its own modules (bundled_module).
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType

from soup.core.contracts import SoupPlugin
from soup.core.packages import ORIGIN_BUNDLED, PackageSource, load_manifest, plugin_factory
from soup.core.packages.loader import import_server_module
from soup.core.settings import DEFAULT_BUNDLED_PACKAGES_DIR

BUNDLED_PACKAGES_DIR = Path(DEFAULT_BUNDLED_PACKAGES_DIR)


def bundled_source(name: str) -> PackageSource:
    path = BUNDLED_PACKAGES_DIR / name
    return PackageSource(load_manifest(path), path, ORIGIN_BUNDLED)


def _import_with_requires(name: str) -> PackageSource:
    """Import the package's server module, after the ones it requires (as the PackageManager loads them)."""

    source = bundled_source(name)
    for required in source.manifest.requires:
        _import_with_requires(required)
    import_server_module(source)
    return source


def bundled_api(name: str) -> ModuleType:
    source = _import_with_requires(name)
    return importlib.import_module(f"{source.manifest.module_name}.api")


def bundled_module(name: str, module: str) -> ModuleType:
    """soup_pkg_<name>.<module>, for the tests of the package itself."""

    source = _import_with_requires(name)
    return importlib.import_module(f"{source.manifest.module_name}.{module}")


def bundled_plugin(name: str) -> SoupPlugin:
    return plugin_factory(_import_with_requires(name))()
