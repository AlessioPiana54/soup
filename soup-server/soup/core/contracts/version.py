"""
------------------------------------------------------------------------
File : version.py
Description: Version of the stable contracts exposed by the host to
             packages, as "MAJOR.MINOR". Packages declare the contracts
             version they were built against (api_version in
             soup-package.json, SoupPlugin.api_version).

             Compatibility rule: a package is compatible when it has the
             same MAJOR as the host and a MINOR lower than or equal to the
             host's. A minor release only adds to the contracts, so a
             host "4.1" would accept packages "4.0" and "4.1"; a host
             "4.0" refuses "4.1" (needs something the host does not have
             yet) and any other major ("3.x", "5.0"), which may have
             removed or changed something.

             History: "3.0" (commit 8) removed add_input_reader,
             add_input_handler and add_build_step from PluginContext (the
             event log and the EKG moved to the ekg package; build steps
             are contributed to its "ekg.build_steps" extension point), so
             packages written for "2.x" no longer load. "3.1" (commit 10)
             added Exporter.applies(obj, tools), so an exporter can be
             offered only for some objects of a kind; "3.0" packages load
             unchanged. "4.0" (commit 11) removed Query, ident and
             GraphDatabase from soup.core.contracts: they belong to the
             tool_memgraph package (soup_pkg_tool_memgraph.api, re-exported
             by soup_pkg_ekg.api), so a "3.x" package importing them from
             the contracts no longer loads. "4.1" (commit 12) added
             Exporter.file_type(obj, params) -> (extension, mime), so the
             exported file can take the extension and the MIME type of
             the object (default: the exporter's extension and mime);
             "4.0" packages load unchanged.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import re

CONTRACTS_API_VERSION = "4.1"

_API_VERSION_RE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")


def parse_api_version(value: object) -> tuple[int, int] | None:
    """(major, minor) for a "MAJOR.MINOR" string, None for anything else."""

    if not isinstance(value, str):
        return None
    match = _API_VERSION_RE.match(value)
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2))


def is_api_compatible(package_version: object, host_version: str = CONTRACTS_API_VERSION) -> bool:
    """Same major as the host, minor not above the host's (see the module docstring)."""

    package = parse_api_version(package_version)
    host = parse_api_version(host_version)
    if package is None or host is None:
        return False
    return package[0] == host[0] and package[1] <= host[1]
