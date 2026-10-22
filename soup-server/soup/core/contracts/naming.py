"""
------------------------------------------------------------------------
File : naming.py
Description: validate_name() - the single rule for user-chosen names
             (objects, packages, analyses). Packages may use them as
             path components or Memgraph property values, so anything
             that could escape a folder or hide a resource is rejected.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import re

from soup.core.contracts.errors import ValidationError

MAX_NAME_LENGTH = 128

_SEPARATORS_RE = re.compile(r"[\\/]")
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")


def validate_name(name: object, *, label: str = "Object") -> str:
    """
    Return `name` unchanged if it is acceptable, otherwise raise.

    Rejected: non-strings, "", names longer than MAX_NAME_LENGTH, "." and
    anything containing "..", path separators ("/" and "\\"), control
    characters, leading/trailing whitespace, and names starting with "_"
    (reserved for internal resources).

    :raises ValidationError: naming the offending rule
    """

    if not isinstance(name, str) or name == "":
        raise ValidationError(f"{label} name must not be empty")
    if len(name) > MAX_NAME_LENGTH:
        raise ValidationError(f"{label} name must be at most {MAX_NAME_LENGTH} characters long")
    if name == "." or ".." in name:
        raise ValidationError(f"{label} name must not be '.' or contain '..': {name!r}")
    if _SEPARATORS_RE.search(name):
        raise ValidationError(f"{label} name must not contain path separators: {name!r}")
    if _CONTROL_CHARS_RE.search(name):
        raise ValidationError(f"{label} name must not contain control characters: {name!r}")
    if name != name.strip():
        raise ValidationError(f"{label} name must not start or end with whitespace: {name!r}")
    if name.startswith("_"):
        raise ValidationError(f"{label} name must not start with '_': {name!r}")
    return name
