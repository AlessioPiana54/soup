"""
------------------------------------------------------------------------
File : test_csv_ekg_multiplicity.py
Description: Tests for the multiplicities between entity columns
             (csv_ekg, multiplicity.py; the old NewDatasetComponent's
             calculateMultiplicity): the four results, multi-valued and
             empty cells, and the corrected last if/else, which turned
             "1 to N" and "N to N" into "1 to 1".
Project : soup-packages/csv_ekg
------------------------------------------------------------------------
"""

import pytest

from tests.packages import bundled_api

csv_ekg = bundled_api("csv_ekg")
Table = bundled_api("ekg").Table


def _table(*rows):
    return Table(("a", "b"), tuple(rows))


@pytest.mark.parametrize("rows, expected", [
    ((("o1", "i1"), ("o2", "i2")), ("1", "1", "1 to 1")),
    ((("o1", "i1"), ("o1", "i2")), ("1", "N", "1 to N")),
    ((("o1", "c1"), ("o2", "c1")), ("N", "1", "N to 1")),
    ((("o1", "i1"), ("o1", "i2"), ("o2", "i1")), ("N", "N", "N to N")),
])
def test_the_four_multiplicities(rows, expected):
    assert csv_ekg.multiplicity(_table(*rows), "a", "b") == expected


def test_multi_valued_cells_are_split_on_commas():
    # One order with two items in one cell: 1 to N, as with two rows.
    assert csv_ekg.multiplicity(_table(("o1", "i1, i2")), "a", "b") == ("1", "N", "1 to N")


def test_empty_cells_are_skipped():
    assert csv_ekg.multiplicity(_table(("o1", None), ("o1", "i1"), (None, "i2")), "a", "b") == ("1", "1", "1 to 1")
    assert csv_ekg.multiplicity(_table(("o1", None)), "a", "b")[2] == "0"


def test_the_block_has_one_node_per_column_and_skips_pairs_without_values():
    table = Table(("a", "b", "c"), (("o1", "i1", None), ("o1", "i2", None)))

    block = csv_ekg.multiplicity_block(table, ["a", "b", "c"])

    assert block["type"] == "graph"
    assert [node["id"] for node in block["data"]["nodes"]] == ["a", "b", "c"]
    [edge] = block["data"]["edges"]
    assert (edge["source"], edge["target"], edge["group"], edge["label"]) == ("a", "b", "1 to N", "1 : N")


def test_no_block_with_fewer_than_two_columns():
    assert csv_ekg.multiplicity_block(_table(("o1", "i1")), ["a"]) is None
    assert csv_ekg.multiplicity_block(_table(("o1", "i1")), ["a", "missing"]) is None
