"""
------------------------------------------------------------------------
File : test_dataset_repository.py
Description: Tests for DatasetRepository (ekg package) on the
             tool_storage package's "storage" tool: hostile name
             rejection, config round-trip (preserving unknown keys), files
             and paths matching the legacy volume layout
             (Models/docker_file_manager_model.py, Services/dataset_service.py),
             the analyses under Analyses/ and the list of the datasets.
Project : soup-packages/ekg
------------------------------------------------------------------------
"""

import pytest

from soup.core.contracts import ValidationError
from tests.fakes import InMemoryFileStorage, fake_storage_tool
from tests.packages import bundled_module

DatasetRepository = bundled_module("ekg", "dataset_repository").DatasetRepository


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


def test_analyses_live_in_the_analyses_folder_of_the_dataset(repo, files):
    repo.save_config("orders", {"dataset_name": "orders"})
    repo.save_analysis("orders", "only create", {"filters": ["Create"]})

    assert files.exists("orders/Analyses/only create.json")
    assert repo.analyses("orders") == ["only create"]
    assert repo.load_analysis("orders", "only create") == {"filters": ["Create"]}

    repo.delete_analysis("orders", "only create")
    assert repo.analyses("orders") == []


def test_delete_also_removes_the_analyses(repo, files):
    repo.save_config("orders", {"dataset_name": "orders"})
    repo.save_analysis("orders", "a1", {})

    repo.delete("orders")

    assert files.paths == []


def test_hostile_analysis_names_are_rejected(repo):
    with pytest.raises(ValidationError):
        repo.save_analysis("orders", "../x", {})


def test_datasets_lists_only_folders_with_a_config(repo, files):
    repo.save_config("orders", {"dataset_name": "orders"})
    repo.save_event_log("half", b"events", b"entities")  # no config: not a dataset
    files.write("_catalog/objects/x.json", b"{}")

    assert repo.datasets() == ["orders"]


def test_free_name_adds_a_suffix_when_the_folder_exists(repo):
    assert repo.free_name("orders") == "orders"
    repo.save_config("orders", {})
    repo.save_config("orders_2", {})
    assert repo.free_name("orders") == "orders_3"
