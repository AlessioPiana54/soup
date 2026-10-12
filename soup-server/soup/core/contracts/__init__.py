"""
------------------------------------------------------------------------
File : __init__.py
Description: Public surface of soup.core.contracts - the stable
             interfaces between the host (soup/core) and every extension
             (soup/plugins, soup/infrastructure). Nothing under
             soup/core/contracts imports pandas, neo4j, docker or Flask.
Project : soup-server
------------------------------------------------------------------------
"""

from soup.core.contracts.version import CONTRACTS_API_VERSION
from soup.core.contracts.exceptions import (
    PluginApiVersionError,
    PluginConflictError,
    PluginCycleError,
    PluginDependencyError,
    PluginError,
)
from soup.core.contracts.query import Query, ident
from soup.core.contracts.ports import FileStorage, GraphDatabase
from soup.core.contracts.plugin import PluginContext, SoupPlugin
from soup.core.contracts.tables import Table
from soup.core.contracts.input import EVENT_LOG, InputHandler, InputReader
from soup.core.contracts.event_log import EventLogData, EventLogReader

__all__ = [
    "CONTRACTS_API_VERSION",
    "PluginError",
    "PluginApiVersionError",
    "PluginConflictError",
    "PluginCycleError",
    "PluginDependencyError",
    "Query",
    "ident",
    "FileStorage",
    "GraphDatabase",
    "PluginContext",
    "SoupPlugin",
    "Table",
    "EVENT_LOG",
    "InputHandler",
    "InputReader",
    "EventLogData",
    "EventLogReader",
]
