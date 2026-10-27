"""
------------------------------------------------------------------------
File : test_tables.py
Description: Tests for Table and the pandas conversions (ekg package,
             tables.py; moved from soup-server/tests).
Project : soup-packages/ekg
------------------------------------------------------------------------
"""

import pytest

from tests.packages import bundled_api

_api = bundled_api("ekg")
Table = _api.Table


def test_table_holds_columns_and_rows():
    table = Table(("a", "b"), (("1", "2"), ("3", None)))
    assert table.columns == ("a", "b")
    assert table.rows == (("1", "2"), ("3", None))
    assert len(table) == 2


def test_table_rejects_rows_of_different_length():
    with pytest.raises(ValueError):
        Table(("a", "b"), (("1", "2"), ("3",)))


def test_table_rejects_row_longer_than_columns():
    with pytest.raises(ValueError):
        Table(("a", "b"), (("1", "2", "3"),))


def test_table_rejects_empty_columns():
    with pytest.raises(ValueError):
        Table((), ())


def test_table_rejects_duplicate_columns():
    with pytest.raises(ValueError):
        Table(("a", "a"), ())


def test_table_accepts_list_inputs_and_freezes_to_tuples():
    table = Table(["a", "b"], [["1", "2"]])
    assert table.columns == ("a", "b")
    assert table.rows == (("1", "2"),)


def test_from_records_infers_columns_from_first_record():
    table = Table.from_records([{"a": "1", "b": "2"}, {"a": "3", "b": "4"}])
    assert table.columns == ("a", "b")
    assert table.rows == (("1", "2"), ("3", "4"))


def test_from_records_requires_explicit_columns_when_empty():
    with pytest.raises(ValueError):
        Table.from_records([])


def test_from_rows():
    table = Table.from_rows(["a", "b"], [("1", "2"), ("3", "4")])
    assert table.columns == ("a", "b")
    assert table.rows == (("1", "2"), ("3", "4"))


def test_column_index_and_iter_records():
    table = Table(("a", "b"), (("1", "2"),))
    assert table.column_index("b") == 1
    assert list(table.iter_records()) == [{"a": "1", "b": "2"}]


def test_contains_checks_columns_not_rows():
    table = Table(("a", "b"), ())
    assert "a" in table
    assert "z" not in table


def test_from_dataframe_turns_nan_into_none_and_cells_into_strings():
    import pandas as pd

    frame = pd.DataFrame({"a": ["1", None], 2: ["x", "y"]})
    table = _api.from_dataframe(frame)
    assert table.columns == ("a", "2")
    assert table.rows == (("1", "x"), (None, "y"))


def test_to_dataframe_round_trip():
    table = Table(("a", "b"), (("1", None), ("3", "4")))
    assert _api.from_dataframe(_api.to_dataframe(table)) == table
