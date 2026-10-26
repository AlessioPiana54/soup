"""
------------------------------------------------------------------------
File : test_dataset_repository.py
Description: Tests for DatasetRepository (soup.core.dataset_repository)
             on the tool_storage package's "storage" tool: hostile name
             rejection, config round-trip (preserving unknown keys), and
             files and paths matching the legacy volume layout
             (Models/docker_file_manager_model.py, Services/dataset_service.py).
Project : soup-server
------------------------------------------------------------------------
"""

import pytest

from soup.core.dataset_repository import DatasetRepository
from soup.core.contracts.errors import ValidationError
from tests.fakes import InMemoryFileStorage, fake_storage_tool


@pytest.fixture
def files():
    return InMemoryFileStorage()


@pytest.fixture
def repo(files):
    return DatasetRepository(fake_storage_tool(files))


@pytest.mark.parametrize("hostile_name", ["../etc", "a/b", "..", "", ".", "a\\b", "_catalog", " padded "])
def test_hostile_dataset_names_are_rejected(repo, hostile_name):
    with pytest.raises(ValidationError):
        repo.save_config(hostile_name, {"dataset_name": hostile_name})


def test_save_and_load_event_log(repo, files):
    repo.save_event_log("orders", b"event_id,timestamp,activity_name\n", b"value,type\n")

    storage = files  # white-box check of the underlying layout
    assert storage.exists("orders/orders.csv")
    assert storage.exists("orders/orders_entity.csv")
    assert storage.read("orders/orders.csv") == b"event_id,timestamp,activity_name\n"
    assert storage.read("orders/orders_entity.csv") == b"value,type\n"


def test_config_round_trip_preserves_unknown_keys(repo):
    config = {
        "dataset_name": "orders",
        "dataset_description": "desc",
        "source_format": "csv",
        "some_future_field_this_class_does_not_know_about": {"nested": True},
    }

    repo.save_config("orders", config)
    loaded = repo.load_config("orders")

    assert loaded == config
    assert loaded["some_future_field_this_class_does_not_know_about"] == {"nested": True}


def test_exists_reflects_config_presence(repo):
    assert repo.exists("orders") is False
    repo.save_config("orders", {"dataset_name": "orders"})
    assert repo.exists("orders") is True


def test_delete_removes_every_file_for_the_dataset(repo, files):
    repo.save_event_log("orders", b"events", b"entities")
    repo.save_config("orders", {"dataset_name": "orders"})

    repo.delete("orders")

    assert repo.exists("orders") is False
    assert files.paths == []


def test_delete_does_not_affect_other_datasets(repo):
    repo.save_config("orders", {"dataset_name": "orders"})
    repo.save_config("invoices", {"dataset_name": "invoices"})

    repo.delete("orders")

    assert repo.exists("orders") is False
    assert repo.exists("invoices") is True


def test_container_paths_match_the_legacy_layout(repo):
    # Models/docker_file_manager_model.py: f'/soup/{dataset_name}/{dataset_name}.csv'
    assert repo.events_csv_load_path("orders") == "/soup/orders/orders.csv"
    assert repo.entities_csv_load_path("orders") == "/soup/orders/orders_entity.csv"


def test_container_paths_respect_a_custom_root():
    repo = DatasetRepository(fake_storage_tool(root="/custom"))
    assert repo.events_csv_load_path("orders") == "/custom/orders/orders.csv"
