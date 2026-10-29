"""
------------------------------------------------------------------------
File : test_mapping_validation.py
Description: mapping_problem/validate_mapping and config_mapping_problem
             (ekg package): event_id, timestamp and activity on three
             different, existing columns. A legacy config with one
             column for every role (the "try" dataset of the old
             interface) is refused with a message naming the column and
             the roles; build_ekg refuses such a mapping before staging
             anything.
Project : soup-packages/ekg
------------------------------------------------------------------------
"""

import pytest

from soup.core.contracts import ValidationError
from tests.packages import bundled_api, bundled_module

event_log = bundled_module("ekg", "event_log")
api = bundled_api("ekg")


def test_three_different_columns_are_a_valid_mapping():
    assert event_log.mapping_problem("id", "ts", "act", entities=["Items"], values=["Res"], columns=["id", "ts", "act", "Items", "Res"]) is None


@pytest.mark.parametrize(("roles", "message"), [
    (("Timestamp", "Timestamp", "Timestamp"), "'Timestamp' is used for event_id, timestamp, activity"),
    (("id", "id", "act"), "'id' is used for event_id, timestamp"),
    (("id", "ts", "ts"), "'ts' is used for timestamp, activity"),
])
def test_one_column_for_two_standard_roles_is_refused(roles, message):
    problem = event_log.mapping_problem(*roles)

    assert problem == f"event_id, timestamp and activity must be three different columns: {message}"
    with pytest.raises(ValidationError, match="must be three different columns"):
        event_log.validate_mapping(*roles)


def test_a_missing_role_and_missing_columns_are_refused():
    assert event_log.mapping_problem("id", "", None) == "The mapping has no column for timestamp, activity"
    assert event_log.mapping_problem("id", "ts", "act", entities=["Items"], columns=["id", "ts", "act"]) == (
        "The mapping refers to columns that are not in the data: ['Items']"
    )


def test_a_legacy_config_with_one_column_for_every_role_has_a_problem():
    config = {
        "all_columns": ["EventID", "Activity", "Timestamp", "Item"],
        "standard_columns": ["Timestamp", "Timestamp", "Timestamp"],
        "filtered_columns": ["Timestamp", "Item"],
        "values_columns": ["Timestamp"],
    }

    assert "'Timestamp' is used for event_id, timestamp, activity" in event_log.config_mapping_problem(config)


@pytest.mark.parametrize("config", [
    # Written by build_ekg: the canonical names, the headers of the staged CSV.
    {"all_columns": ["EventID", "Activity", "Timestamp"], "standard_columns": ["event_id", "timestamp", "activity_name"]},
    # The old interface: the original names, among all_columns.
    {"all_columns": ["EventID", "Activity", "Timestamp"], "standard_columns": ["EventID", "Timestamp", "Activity"]},
    # Separated form (OCEL): the entities are object types, not columns of the events.
    {"all_columns": ["ocel:eid"], "standard_columns": ["event_id", "timestamp", "activity_name"],
     "filtered_columns": ["order", "item"]},
    # No standard_columns: the canonical ones.
    {"all_columns": []},
])
def test_valid_configs_have_no_problem(config):
    assert event_log.config_mapping_problem(config) is None


def test_a_config_with_standard_columns_not_in_the_data_or_not_three_has_a_problem():
    assert "not in the data: ['Missing']" in event_log.config_mapping_problem(
        {"all_columns": ["a", "b"], "standard_columns": ["a", "b", "Missing"]})
    assert "exactly 3 standard_columns" in event_log.config_mapping_problem({"standard_columns": ["a", "b"]})


def test_build_ekg_refuses_one_column_for_two_roles_before_anything_else():
    mapping = api.ColumnMapping(event_id="id", timestamp="id", activity="act")

    # No object, data or tools: the mapping is refused before they are used.
    with pytest.raises(ValidationError, match="'id' is used for event_id, timestamp"):
        api.build_ekg(None, None, mapping, None)
