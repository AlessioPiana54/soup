"""
------------------------------------------------------------------------
File : field_validation.py
Description: validate_values() - checks the values a client sent for a
             form (operation/exporter parameters, import options)
             against the Fields the package declared, before the package
             sees them: required fields present, values of the right
             type, choices respected, "items" elements checked against
             their variant. Returns the cleaned values (defaults filled
             in, numeric/boolean strings coerced, undeclared keys
             dropped) or raises one ValidationError listing every
             problem, keyed by field path (e.g. "steps[1].threshold").
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import base64
import binascii
import copy
import math
from datetime import date, datetime
from typing import Any, Mapping, Optional, Sequence

from soup.core.contracts import Field, Upload, ValidationError
from soup.core.contracts import fields as field_types

_TRUE_STRINGS = {"true", "1", "yes", "on"}
_FALSE_STRINGS = {"false", "0", "no", "off"}


class _Invalid(Exception):
    """One field's value is unacceptable; message is user-facing."""


def validate_values(fields: Sequence[Field], values: Optional[Mapping[str, Any]]) -> dict[str, Any]:
    """
    :raises ValidationError: with `details` = {field path: message}
    """

    if values is not None and not isinstance(values, Mapping):
        raise ValidationError("Parameters must be an object")
    errors: dict[str, str] = {}
    cleaned = _validate_fields(fields, values or {}, "", errors)
    if errors:
        summary = "; ".join(f"{path}: {message}" for path, message in errors.items())
        raise ValidationError(f"Invalid parameters - {summary}", details=errors)
    return cleaned


def _validate_fields(
    fields: Sequence[Field], values: Mapping[str, Any], prefix: str, errors: dict[str, str]
) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for spec in fields:
        path = f"{prefix}{spec.name}"
        raw = values.get(spec.name)
        if _is_empty(spec, raw):
            if spec.required:
                errors[path] = "is required"
            else:
                cleaned[spec.name] = copy.deepcopy(spec.default)
            continue
        try:
            cleaned[spec.name] = _validate_value(spec, raw, path, errors)
        except _Invalid as exc:
            errors[path] = str(exc)
    return cleaned


def _is_empty(spec: Field, raw: Any) -> bool:
    if raw is None:
        return True
    if isinstance(raw, str) and raw.strip() == "" and spec.type != field_types.BOOL:
        return True
    if spec.type in field_types.LIST_FIELD_TYPES and isinstance(raw, (list, tuple)) and len(raw) == 0:
        return True
    return False


def _validate_value(spec: Field, raw: Any, path: str, errors: dict[str, str]) -> Any:
    kind = spec.type
    if kind in (field_types.TEXT, field_types.TEXTAREA):
        return _string(raw)
    if kind == field_types.NUMBER:
        return _number(raw)
    if kind == field_types.BOOL:
        return _boolean(raw)
    if kind in (field_types.SELECT, field_types.COLUMN):
        return _one_of(spec, _string(raw))
    if kind in (field_types.MULTISELECT, field_types.COLUMNS):
        return _unique([_one_of(spec, _string(item)) for item in _list(raw)])
    if kind == field_types.PAIRS:
        return [_pair(spec, item) for item in _list(raw)]
    if kind == field_types.DATE:
        return _date(raw)
    if kind == field_types.DATETIME:
        return _datetime(raw)
    if kind == field_types.FILE:
        return _file(raw)
    if kind == field_types.ITEMS:
        return _items(spec, raw, path, errors)
    raise _Invalid(f"unsupported field type {kind!r}")  # unreachable: Field rejects unknown types


def _string(raw: Any) -> str:
    if not isinstance(raw, str):
        raise _Invalid("must be a string")
    return raw


def _number(raw: Any) -> float | int:
    if isinstance(raw, bool):
        raise _Invalid("must be a number")
    value: float | int
    if isinstance(raw, (int, float)):
        value = raw
    elif isinstance(raw, str):
        text = raw.strip()
        try:
            value = int(text)
        except ValueError:
            try:
                value = float(text)
            except ValueError:
                raise _Invalid("must be a number") from None
    else:
        raise _Invalid("must be a number")
    if isinstance(value, float) and not math.isfinite(value):
        raise _Invalid("must be a finite number")
    return value


def _boolean(raw: Any) -> bool:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, int) and raw in (0, 1):
        return bool(raw)
    if isinstance(raw, str):
        text = raw.strip().lower()
        if text in _TRUE_STRINGS:
            return True
        if text in _FALSE_STRINGS:
            return False
    raise _Invalid("must be true or false")


def _one_of(spec: Field, value: str) -> str:
    allowed = spec.choice_values()
    if allowed and value not in allowed:
        raise _Invalid(f"{value!r} is not one of {list(allowed)}")
    return value


def _list(raw: Any) -> list[Any]:
    if not isinstance(raw, (list, tuple)):
        raise _Invalid("must be a list")
    return list(raw)


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _pair(spec: Field, raw: Any) -> list[str]:
    if not isinstance(raw, (list, tuple)) or len(raw) != 2:
        raise _Invalid("every element must be a pair [first, second]")
    return [_one_of(spec, _string(raw[0])), _one_of(spec, _string(raw[1]))]


def _date(raw: Any) -> str:
    text = _string(raw).strip()
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        raise _Invalid("must be a date (YYYY-MM-DD)") from None


def _datetime(raw: Any) -> str:
    text = _string(raw).strip()
    try:
        datetime.fromisoformat(text)
    except ValueError:
        raise _Invalid("must be an ISO-8601 date-time") from None
    return text


def _file(raw: Any) -> Upload:
    if isinstance(raw, Upload):
        return raw
    if isinstance(raw, Mapping) and isinstance(raw.get("filename"), str) and isinstance(raw.get("base64"), str):
        try:
            content = base64.b64decode(raw["base64"], validate=True)
        except (binascii.Error, ValueError):
            raise _Invalid("file content is not valid base64") from None
        return Upload.from_bytes(raw["filename"], content, str(raw.get("content_type") or ""))
    raise _Invalid("must be a file")


def _items(spec: Field, raw: Any, path: str, errors: dict[str, str]) -> list[dict[str, Any]]:
    result = []
    for index, element in enumerate(_list(raw)):
        element_path = f"{path}[{index}]"
        if not isinstance(element, Mapping):
            errors[element_path] = "must be an object {variant, values}"
            continue
        key = element.get("variant")
        variant = spec.variant(key) if isinstance(key, str) else None
        if variant is None:
            errors[f"{element_path}.variant"] = f"must be one of {[v.key for v in spec.variants]}"
            continue
        element_values = element.get("values") or {}
        if not isinstance(element_values, Mapping):
            errors[f"{element_path}.values"] = "must be an object"
            continue
        values = _validate_fields(variant.fields, element_values, f"{element_path}.", errors)
        result.append({"variant": variant.key, "values": values})
    return result
