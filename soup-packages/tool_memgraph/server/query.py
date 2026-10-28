"""
------------------------------------------------------------------------
File : query.py
Description: Query value object and ident() helper - moved here from
             soup/core/contracts/query.py, which keeps a temporary copy
             for the legacy core modules. Together they are the
             only way packages are meant to build Cypher: dynamic
             *values* always travel as Query.params (never interpolated
             into the text), and dynamic *identifiers* (labels, property
             keys, relationship types - which Cypher cannot bind as query
             parameters) must go through ident(), which validates them
             against a strict allow-list before quoting them.
             This module intentionally has zero dependencies (no pandas,
             no neo4j, no Flask): it is a pure value-object contract.
Project : soup-packages/tool_memgraph
------------------------------------------------------------------------
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class Query:
    """
    Immutable value object representing a parameterized Cypher query: the
    query text (with $placeholders for every dynamic value) and the
    parameters bound to it. Never build `text` by interpolating user input.
    """

    text: str
    params: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("Query.text must be a non-empty string")
        if not isinstance(self.params, Mapping):
            raise ValueError("Query.params must be a mapping")
        # Defensive copy so external mutation of the dict passed in cannot
        # reach back into this (conceptually immutable) value object.
        object.__setattr__(self, "params", dict(self.params))


def ident(name: str) -> str:
    """
    Validate and quote a Cypher identifier (node label, relationship type,
    or property key). These cannot be bound as query parameters in Cypher,
    so any identifier built from external input must be validated here
    instead of interpolated directly into query text.

    Accepts only names that start with a letter or underscore and contain
    only letters, digits and underscores - rejecting anything that could
    break out of a backtick-quoted identifier or inject additional Cypher
    (spaces, backticks, semicolons, dots, dashes, quotes, ...).

    :param name: the raw identifier
    :return: the identifier quoted with backticks, safe to splice into
             query text (e.g. f"MATCH (n:{ident(label)})")
    :raises ValueError: if `name` is not a valid simple identifier
    """

    if not isinstance(name, str) or not name:
        raise ValueError(f"Invalid Cypher identifier: {name!r}")
    if not _IDENT_RE.match(name):
        raise ValueError(f"Invalid Cypher identifier: {name!r}")
    return f"`{name}`"
