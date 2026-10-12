"""
------------------------------------------------------------------------
File : test_fakes.py
Description: Tests for the in-memory fakes used by other tests
             (tests.fakes.InMemoryFileStorage, tests.fakes.FakeDatabase).
Project : soup-server
------------------------------------------------------------------------
"""

import pytest

from soup.core.contracts import Query
from tests.fakes import FakeDatabase, InMemoryFileStorage


def test_in_memory_file_storage_round_trip():
    storage = InMemoryFileStorage()

    assert storage.exists("a/b.csv") is False

    storage.write("a/b.csv", b"col1,col2\n1,2\n")
    assert storage.exists("a/b.csv") is True
    assert storage.read("a/b.csv") == b"col1,col2\n1,2\n"

    storage.delete("a/b.csv")
    assert storage.exists("a/b.csv") is False


def test_in_memory_file_storage_read_missing_raises():
    storage = InMemoryFileStorage()
    with pytest.raises(FileNotFoundError):
        storage.read("missing.csv")


def test_in_memory_file_storage_list_with_prefix():
    storage = InMemoryFileStorage()
    storage.write("orders/order_1.csv", b"x")
    storage.write("orders/order_2.csv", b"y")
    storage.write("invoices/invoice_1.csv", b"z")

    assert storage.list("orders/") == ["orders/order_1.csv", "orders/order_2.csv"]
    assert storage.list() == [
        "invoices/invoice_1.csv",
        "orders/order_1.csv",
        "orders/order_2.csv",
    ]


def test_fake_database_records_text_and_params_in_order():
    db = FakeDatabase()

    db.run(Query("MATCH (n) RETURN n", {"id": "e1"}))
    db.run(Query("MATCH (m) RETURN m"))

    assert len(db.received_queries) == 2
    assert db.received_queries[0].text == "MATCH (n) RETURN n"
    assert db.received_queries[0].params == {"id": "e1"}
    assert db.received_queries[1].text == "MATCH (m) RETURN m"
    assert db.received_queries[1].params == {}


def test_fake_database_returns_configured_response():
    db = FakeDatabase()
    db.set_response("MATCH (n) RETURN n", [{"id": "e1"}, {"id": "e2"}])
    db.set_default_response([{"default": True}])

    configured = db.run(Query("MATCH (n) RETURN n"))
    default = db.run(Query("MATCH (other) RETURN other"))

    assert configured == [{"id": "e1"}, {"id": "e2"}]
    assert default == [{"default": True}]
