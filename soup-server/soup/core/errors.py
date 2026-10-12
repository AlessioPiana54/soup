"""
------------------------------------------------------------------------
File : errors.py
Description: Domain exceptions carrying an HTTP status code, so the API
             adapter (soup/api, not built in this session) can translate
             them to a response in one place instead of each service
             repeating its own try/except + jsonify(..., status).
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations


class DomainError(Exception):
    """Base class for every domain error; carries the HTTP status to report."""

    http_status_code: int = 500


class ValidationError(DomainError):
    """The request/input is well-formed but fails a domain rule (400)."""

    http_status_code = 400


class NotFoundError(DomainError):
    """The referenced resource does not exist (404)."""

    http_status_code = 404


class ConflictError(DomainError):
    """The request conflicts with the current state of a resource (409)."""

    http_status_code = 409
