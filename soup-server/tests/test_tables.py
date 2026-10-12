"""
------------------------------------------------------------------------
File : test_tables.py
Description: Tests for Table (soup.core.contracts.tables).
Project : soup-server
------------------------------------------------------------------------
"""

import pytest

from soup.core.contracts import Table


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
