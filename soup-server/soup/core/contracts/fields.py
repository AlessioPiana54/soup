"""
------------------------------------------------------------------------
File : fields.py
Description: Field - one input of a form the frontend generates from
             what an Importer (inspect), an Operation or an Exporter
             (fields) declares. The set of field types is closed: the
             frontend knows how to render each of them, a package only
             picks one and fills in labels, choices and defaults. Values
             are checked by the core (soup/core/field_validation.py)
             before they reach the package.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Optional, Union

TEXT = "text"
TEXTAREA = "textarea"
NUMBER = "number"
BOOL = "bool"
SELECT = "select"
MULTISELECT = "multiselect"
COLUMN = "column"
COLUMNS = "columns"
PAIRS = "pairs"
DATE = "date"
DATETIME = "datetime"
FILE = "file"
ITEMS = "items"

FIELD_TYPES = (
    TEXT, TEXTAREA, NUMBER, BOOL, SELECT, MULTISELECT, COLUMN, COLUMNS,
    PAIRS, DATE, DATETIME, FILE, ITEMS,
)

# Types whose value is a list (an empty list counts as "no value").
LIST_FIELD_TYPES = (MULTISELECT, COLUMNS, PAIRS, ITEMS)

# Types that must declare their choices up front.
_CHOICE_REQUIRED_TYPES = (SELECT, MULTISELECT)


@dataclass(frozen=True)
class Choice:
    """One selectable value; `label` defaults to the value itself."""

    value: str
    label: str = ""

    def __post_init__(self) -> None:
        if not self.label:
            object.__setattr__(self, "label", self.value)

    def to_dict(self) -> dict[str, Any]:
        return {"value": self.value, "label": self.label}


ChoiceLike = Union[Choice, str, dict]


def _to_choice(raw: ChoiceLike) -> Choice:
    if isinstance(raw, Choice):
        return raw
    if isinstance(raw, str):
        return Choice(raw)
    if isinstance(raw, dict):
        return Choice(str(raw["value"]), str(raw.get("label") or ""))
    raise ValueError(f"Invalid choice: {raw!r}")


@dataclass(frozen=True)
class Field:
    """
    Types and the value each one expects:

    - text, textarea: a string.
    - number: an int or float (numeric strings are accepted).
    - bool: true/false ("true"/"false"/"1"/"0" are accepted).
    - select: one of `choices`; multiselect: a list of `choices`.
    - column: one column of the preview; columns: a list of them. When
      `choices` is set it restricts the allowed columns, otherwise any
      string is accepted (the frontend offers the preview's columns).
    - pairs: a list of [first, second] pairs (e.g. trigger/target); when
      `choices` is set, both elements must be among them.
    - date: "YYYY-MM-DD"; datetime: an ISO-8601 date-time.
    - file: the content of a file chosen by the user (an Upload, or
      {"filename", "base64", "content_type"?} when sent as JSON).
    - items: a list composed by the user (generic AnalysisDraft), where
      each element is {"variant": <Variant.key>, "values": {...}} and
      `values` are checked against that variant's own `fields`.
    """

    name: str
    label: str = ""
    type: str = TEXT
    required: bool = False
    default: Any = None
    choices: tuple[Choice, ...] = ()
    help: str = ""
    variants: tuple["Variant", ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("Field.name must be a non-empty string")
        if self.type not in FIELD_TYPES:
            raise ValueError(f"Field '{self.name}': unknown type {self.type!r}; expected one of {FIELD_TYPES}")
        if not self.label:
            object.__setattr__(self, "label", self.name)

        choices = tuple(_to_choice(choice) for choice in (self.choices or ()))
        object.__setattr__(self, "choices", choices)
        if self.type in _CHOICE_REQUIRED_TYPES and not choices:
            raise ValueError(f"Field '{self.name}' of type {self.type!r} needs at least one choice")

        variants = tuple(self.variants or ())
        object.__setattr__(self, "variants", variants)
        if self.type == ITEMS:
            if not variants:
                raise ValueError(f"Field '{self.name}' of type 'items' needs at least one variant")
            keys = [variant.key for variant in variants]
            if len(set(keys)) != len(keys):
                raise ValueError(f"Field '{self.name}': duplicate variant keys {keys}")
        elif variants:
            raise ValueError(f"Field '{self.name}': only 'items' fields can declare variants")

    def choice_values(self) -> tuple[str, ...]:
        return tuple(choice.value for choice in self.choices)

    def variant(self, key: str) -> Optional["Variant"]:
        return next((variant for variant in self.variants if variant.key == key), None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "type": self.type,
            "required": self.required,
            "default": None if self.type == FILE else self.default,
            "choices": [choice.to_dict() for choice in self.choices],
            "help": self.help,
            "variants": [variant.to_dict() for variant in self.variants],
        }


@dataclass(frozen=True)
class Variant:
    """One kind of element of an "items" field, with its own fields."""

    key: str
    label: str = ""
    description: str = ""
    fields: tuple[Field, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.key, str) or not self.key:
            raise ValueError("Variant.key must be a non-empty string")
        if not self.label:
            object.__setattr__(self, "label", self.key)
        object.__setattr__(self, "fields", tuple(self.fields or ()))
        check_unique_names(self.fields, f"variant '{self.key}'")

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "description": self.description,
            "fields": [item.to_dict() for item in self.fields],
        }


def check_unique_names(fields: Iterable[Field], where: str) -> None:
    names = [item.name for item in fields]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise ValueError(f"Duplicate field names in {where}: {duplicates}")
