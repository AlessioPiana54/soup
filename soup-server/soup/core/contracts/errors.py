"""
------------------------------------------------------------------------
File : errors.py
Description: Domain exceptions carrying an HTTP status code. They live
             among the contracts because packages raise them too (an
             importer rejecting its options, a visualizer asked for an
             unknown action): the core and the packages raise them, and
             only soup/api translates them into an HTTP response, in one
             place.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class DomainError(Exception):
    """
    Base class for every domain error; carries the HTTP status to report.
    `details` is optional structured information (e.g. one message per
    invalid field) that the API layer may add to the response.
    """

    http_status_code: int = 500

    def __init__(self, message: str = "", details: Mapping[str, Any] | None = None):
        super().__init__(message)
        self.details: dict[str, Any] = dict(details or {})


class ValidationError(DomainError):
    """The request/input is well-formed but fails a domain rule (400)."""

    http_status_code = 400


class NotFoundError(DomainError):
    """The referenced resource does not exist (404)."""

    http_status_code = 404


class ForbiddenError(DomainError):
    """The operation is not allowed by the server's configuration (403)."""

    http_status_code = 403


class ConflictError(DomainError):
    """The request conflicts with the current state of a resource (409)."""

    http_status_code = 409


class ServiceUnavailableError(DomainError):
    """
    A service cannot answer because a tool it needs is not available,
    e.g. no loaded package provides the object catalog (503).
    """

    http_status_code = 503
