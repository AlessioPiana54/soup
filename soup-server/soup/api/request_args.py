"""
------------------------------------------------------------------------
File : request_args.py
Description: Reading the current Flask request for the /api/v3 routes:
             the uploaded file as an Upload, required form fields and
             query arguments, JSON form fields and bodies, boolean flags,
             the ?objects=id1,id2 selection (or the "objects" of a JSON
             body) and the parameters of a GET
             (?params=<json> or the flat query arguments). Anything
             missing or malformed raises ValidationError (400), so every
             error goes through the single handler with the same
             envelope instead of Werkzeug's HTML 400.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import json
from typing import Any, BinaryIO, cast

from flask import request
from werkzeug.datastructures import FileStorage

from soup.core.contracts import Upload, ValidationError

_TRUE_VALUES = {"1", "true", "yes", "on"}


def flag(name: str) -> bool:
    value = request.values.get(name, "")
    return value.strip().lower() in _TRUE_VALUES


def uploaded_file(field: str = "file") -> FileStorage:
    file = request.files.get(field)
    if file is None or not file.filename:
        raise ValidationError(f"Missing file (multipart field '{field}')")
    return file


def upload(field: str = "file") -> Upload:
    file = uploaded_file(field)
    # werkzeug types the stream as IO[bytes]: a binary file, what Upload reads.
    return Upload(file.filename or "", cast(BinaryIO, file.stream), file.mimetype or "")


def required_form(name: str) -> str:
    value = request.form.get(name)
    if value is None or not value.strip():
        raise ValidationError(f"Missing form field '{name}'")
    return value


def required_arg(name: str) -> str:
    value = request.args.get(name)
    if value is None or not value.strip():
        raise ValidationError(f"Missing query argument '{name}'")
    return value


def _parse_json(raw: str, what: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{what} is not valid JSON: {exc}") from None


def json_form(name: str) -> dict[str, Any]:
    """A form field holding a JSON object; absent or empty means {}."""

    raw = request.form.get(name)
    if raw is None or not raw.strip():
        return {}
    value = _parse_json(raw, f"Form field '{name}'")
    if not isinstance(value, dict):
        raise ValidationError(f"Form field '{name}' must be a JSON object")
    return value


def json_body() -> dict[str, Any]:
    """The request body as a JSON object; an empty body means {}."""

    if not request.get_data(cache=True):
        return {}
    value = request.get_json(silent=True, force=True)
    if not isinstance(value, dict):
        raise ValidationError("The request body must be a JSON object")
    return value


def object_ids() -> list[str]:
    """The selection ?objects=id1,id2 (at least one id)."""

    ids = [item.strip() for item in request.args.get("objects", "").split(",") if item.strip()]
    if not ids:
        raise ValidationError("Missing query argument 'objects' (comma-separated object ids)")
    return ids


def query_params() -> dict[str, Any]:
    """?params=<JSON object> if given, otherwise the flat query arguments."""

    raw = request.args.get("params")
    if raw is None:
        return dict(request.args.to_dict())
    value = _parse_json(raw, "Query argument 'params'")
    if not isinstance(value, dict):
        raise ValidationError("Query argument 'params' must be a JSON object")
    return value


def selection(body: dict[str, Any]) -> Any:
    """`objects` of a JSON body: a non-empty list of ids or a {slot name: id} mapping."""

    objects = body.get("objects")
    if isinstance(objects, list) and objects and all(isinstance(item, str) for item in objects):
        return objects
    if isinstance(objects, dict) and objects and all(
        isinstance(key, str) and isinstance(value, str) for key, value in objects.items()
    ):
        return objects
    raise ValidationError("'objects' must be a non-empty list of object ids or a {slot: object id} mapping")
