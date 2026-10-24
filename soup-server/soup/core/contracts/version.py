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
             host "2.1" accepts packages "2.0" and "2.1"; it refuses
             "2.2" (needs something the host does not have yet) and any
             other major ("1.x", "3.0"), which may have removed or changed
             something.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import re
from typing import Optional

CONTRACTS_API_VERSION = "2.0"

_API_VERSION_RE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")


def parse_api_version(value: object) -> Optional[tuple[int, int]]:
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
