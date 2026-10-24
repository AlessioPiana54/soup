"""
------------------------------------------------------------------------
File : packages.py
Description: Access to the packages shipped in soup-packages/ from the
             tests, through the same isolated import the PackageManager
             uses (soup_pkg_<name>). Tests reach a package only through
             its public api.py, like another package would.
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


def bundled_api(name: str) -> ModuleType:
    source = bundled_source(name)
    import_server_module(source)
    return importlib.import_module(f"{source.manifest.module_name}.api")


def bundled_plugin(name: str) -> SoupPlugin:
    return plugin_factory(bundled_source(name))()
