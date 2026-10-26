"""
------------------------------------------------------------------------
File : api.py
Description: Public API of the tool_storage package. Other packages
             import it as soup_pkg_tool_storage.api, and only if they list
             "tool_storage" in their `requires`; using the tools only
             needs "storage" (or "catalog", "preferences") in
             `requires_tools`.
Project : soup-packages/tool_storage
------------------------------------------------------------------------
"""

from .catalog import FileCatalog
from .preferences import FilePreferences
from .storage import STORAGE_TOOL, StorageSpace, StorageTool

__all__ = ["STORAGE_TOOL", "FileCatalog", "FilePreferences", "StorageSpace", "StorageTool"]
