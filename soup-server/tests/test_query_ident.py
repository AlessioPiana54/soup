"""
------------------------------------------------------------------------
File : test_query_ident.py
Description: Tests for the Query value object and the ident() identifier
             guard (soup.core.contracts.query).
Project : soup-server
------------------------------------------------------------------------
"""

import dataclasses

import pytest

from soup.core.contracts import Query, ident


def test_query_holds_text_and_params():
    query = Query("MATCH (n) WHERE n.id = $id RETURN n", {"id": "e1"})
    assert query.text == "MATCH (n) WHERE n.id = $id RETURN n"
    assert query.params == {"id": "e1"}


def test_query_defaults_params_to_empty_dict():
    query = Query("RETURN 1")
    assert query.params == {}


def test_query_is_a_frozen_dataclass():
    query = Query("RETURN 1")
    assert dataclasses.is_dataclass(query)
    with pytest.raises(dataclasses.FrozenInstanceError):
        query.text = "RETURN 2"  # type: ignore[misc]


def test_query_copies_params_defensively():
    original_params = {"a": 1}
    query = Query("RETURN $a", original_params)
    original_params["a"] = 999
    assert query.params == {"a": 1}


@pytest.mark.parametrize("bad_text", ["", "   "])
def test_query_rejects_empty_text(bad_text):
    with pytest.raises(ValueError):
        Query(bad_text)


@pytest.mark.parametrize("name", ["Event", "Event_Id", "_private", "a1b2", "DF_C"])
def test_ident_accepts_simple_identifiers(name):
    assert ident(name) == f"`{name}`"


@pytest.mark.parametrize(
    "hostile",
    [
        "",
        "1abc",               # cannot start with a digit
        "a b",                # space
        "a-b",                # dash
        "a.b",                # dot (property path)
        "a;DROP TABLE",       # statement injection attempt
        "a`b",                # breaks out of backtick quoting
        "a$b",                # dollar sign
        "a'b",
        'a"b',
        "a\nb",
        None,
        123,
    ],
)
def test_ident_rejects_hostile_or_invalid_input(hostile):
    with pytest.raises(ValueError):
        ident(hostile)
