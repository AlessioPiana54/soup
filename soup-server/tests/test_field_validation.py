"""
------------------------------------------------------------------------
File : test_field_validation.py
Description: Tests for Field declarations and validate_values(): every
             field type, defaults, required fields, and "items" fields
             whose elements pick a variant with its own fields (generic
             AnalysisDraft, scheda C28).
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import base64

import pytest

from soup.core.contracts import Field, Upload, ValidationError, Variant
from soup.core.field_validation import validate_values

STEPS = Field(
    "steps",
    type="items",
    required=True,
    variants=(
        Variant(
            "filter",
            "Filter",
            "Keep only some activities",
            fields=(
                Field("activities", type="multiselect", required=True, choices=("Create", "Ship", "Pay")),
                Field("keep", type="bool", default=True),
            ),
        ),
        Variant(
            "aggregate",
            "Aggregate",
            fields=(
                Field("by", type="column", required=True),
                Field("threshold", type="number", default=0),
            ),
        ),
    ),
)


def _details(fields, values):
    with pytest.raises(ValidationError) as invalid:
        validate_values(fields, values)
    assert invalid.value.http_status_code == 400
    return invalid.value.details


def test_items_elements_are_validated_against_their_variant():
    cleaned = validate_values(
        [STEPS],
        {
            "steps": [
                {"variant": "filter", "values": {"activities": ["Ship", "Create", "Ship"]}},
                {"variant": "aggregate", "values": {"by": "customer", "threshold": "2.5"}},
            ]
        },
    )

    assert cleaned == {
        "steps": [
            {"variant": "filter", "values": {"activities": ["Ship", "Create"], "keep": True}},
            {"variant": "aggregate", "values": {"by": "customer", "threshold": 2.5}},
        ]
    }


def test_items_errors_name_the_element_and_its_field():
    details = _details(
        [STEPS],
        {
            "steps": [
                {"variant": "filter", "values": {}},
                {"variant": "aggregate", "values": {"by": "c", "threshold": "x"}},
                {"variant": "explode", "values": {}},
                "not an object",
                {"variant": "filter", "values": {"activities": ["Fly"]}},
            ]
        },
    )

    assert details == {
        "steps[0].activities": "is required",
        "steps[1].threshold": "must be a number",
        "steps[2].variant": "must be one of ['filter', 'aggregate']",
        "steps[3]": "must be an object {variant, values}",
        "steps[4].activities": "'Fly' is not one of ['Create', 'Ship', 'Pay']",
    }


def test_required_items_field_cannot_be_empty():
    assert _details([STEPS], {"steps": []}) == {"steps": "is required"}


def test_defaults_fill_missing_optional_fields_and_unknown_keys_are_dropped():
    fields = [Field("title", default="Untitled"), Field("tags", type="columns", default=["a"])]

    cleaned = validate_values(fields, {"unknown": 1})
    cleaned["tags"].append("mutated")

    assert cleaned == {"title": "Untitled", "tags": ["a", "mutated"]}
    assert fields[1].default == ["a"]  # defaults are copied, not shared


@pytest.mark.parametrize(
    "field, raw, expected",
    [
        (Field("t", type="text"), "hello", "hello"),
        (Field("t", type="textarea"), "a\nb", "a\nb"),
        (Field("n", type="number"), "3", 3),
        (Field("n", type="number"), 1.5, 1.5),
        (Field("b", type="bool"), "false", False),
        (Field("b", type="bool"), True, True),
        (Field("s", type="select", choices=("x", "y")), "y", "y"),
        (Field("c", type="column", choices=("id", "ts")), "ts", "ts"),
        (Field("c", type="column"), "anything", "anything"),
        (Field("p", type="pairs", choices=("A", "B")), [["A", "B"], ("B", "A")], [["A", "B"], ["B", "A"]]),
        (Field("d", type="date"), "2025-01-31", "2025-01-31"),
        (Field("dt", type="datetime"), "2025-01-31T10:00:00", "2025-01-31T10:00:00"),
    ],
)
def test_valid_values_per_type(field, raw, expected):
    assert validate_values([field], {field.name: raw}) == {field.name: expected}


@pytest.mark.parametrize(
    "field, raw",
    [
        (Field("t", type="text"), 12),
        (Field("n", type="number"), True),
        (Field("n", type="number"), "nan"),
        (Field("b", type="bool"), "maybe"),
        (Field("s", type="select", choices=("x",)), "z"),
        (Field("m", type="multiselect", choices=("x",)), "x"),
        (Field("p", type="pairs"), [["only-one"]]),
        (Field("d", type="date"), "31/01/2025"),
        (Field("dt", type="datetime"), "yesterday"),
        (Field("f", type="file"), "C:/secret.txt"),
        (Field("f", type="file"), {"filename": "a.csv", "base64": "%%%"}),
    ],
)
def test_invalid_values_per_type(field, raw):
    assert set(_details([field], {field.name: raw})) == {field.name}


def test_file_field_accepts_an_upload_or_base64_json():
    file = Upload.from_bytes("a.csv", b"1,2")
    field = Field("f", type="file", required=True)

    assert validate_values([field], {"f": file})["f"] is file

    decoded = validate_values([field], {"f": {"filename": "b.csv", "base64": base64.b64encode(b"x,y").decode()}})["f"]
    assert (decoded.filename, decoded.read()) == ("b.csv", b"x,y")


def test_params_must_be_an_object():
    with pytest.raises(ValidationError):
        validate_values([Field("t")], ["not", "a", "dict"])  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "build",
    [
        lambda: Field("x", type="unknown"),
        lambda: Field(""),
        lambda: Field("s", type="select"),
        lambda: Field("i", type="items"),
        lambda: Field("t", type="text", variants=(Variant("v"),)),
        lambda: Field("i", type="items", variants=(Variant("v"), Variant("v"))),
        lambda: Variant("v", fields=(Field("a"), Field("a"))),
    ],
)
def test_invalid_field_declarations_are_refused(build):
    with pytest.raises(ValueError):
        build()


def test_field_serializes_choices_and_variants_for_the_frontend():
    data = STEPS.to_dict()

    assert data["type"] == "items"
    assert data["variants"][0]["key"] == "filter"
    assert data["variants"][0]["fields"][0]["choices"][0] == {"value": "Create", "label": "Create"}
    assert data["variants"][1]["label"] == "Aggregate"
