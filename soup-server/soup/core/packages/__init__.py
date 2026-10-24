"""
------------------------------------------------------------------------
File : __init__.py
Description: soup.core.packages - packages on disk (soup-package.json +
             server/ + app/), their discovery, isolated import, persisted
             state and runtime lifecycle (PackageManager).
Project : soup-server
------------------------------------------------------------------------
"""

from soup.core.packages.archive import ArchiveLimits
from soup.core.packages.discovery import ORIGIN_BUNDLED, ORIGIN_INSTALLED, PackageSource, discover_packages
from soup.core.packages.loader import plugin_factory, purge
from soup.core.packages.manager import (
    STATUS_ACTIVE,
    STATUS_DISABLED,
    STATUS_FAILED,
    STATUS_MISSING,
    PackageInfo,
    PackageManager,
    PackageManagerConfig,
)
from soup.core.packages.manifest import MANIFEST_FILE, PackageManifest, load_manifest, parse_manifest

__all__ = [
    "ArchiveLimits",
    "ORIGIN_BUNDLED",
    "ORIGIN_INSTALLED",
    "PackageSource",
    "discover_packages",
    "plugin_factory",
    "purge",
    "STATUS_ACTIVE",
    "STATUS_DISABLED",
    "STATUS_FAILED",
    "STATUS_MISSING",
    "PackageInfo",
    "PackageManager",
    "PackageManagerConfig",
    "MANIFEST_FILE",
    "PackageManifest",
    "load_manifest",
    "parse_manifest",
]
