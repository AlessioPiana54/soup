"""
------------------------------------------------------------------------
File : test_registry.py
Description: Tests for the generic Registry[T] (soup.core.registry).
Project : soup-server
------------------------------------------------------------------------
"""

import pytest

from soup.core.contracts import PluginConflictError
from soup.core.registry import Registry


def test_register_and_get():
    registry: Registry[str] = Registry("thing")
    registry.register("value-a", owner="plugin_a", key="a")

    assert registry.get("a") == "value-a"
    assert registry.owner_of("a") == "plugin_a"
    assert "a" in registry
    assert len(registry) == 1


def test_get_missing_key_returns_none():
    registry: Registry[str] = Registry("thing")
    assert registry.get("missing") is None


def test_duplicate_key_raises_conflict_naming_both_plugins():
    registry: Registry[str] = Registry("thing")
    registry.register("value-a", owner="plugin_a", key="shared")

    with pytest.raises(PluginConflictError) as exc_info:
        registry.register("value-b", owner="plugin_b", key="shared")

    error = exc_info.value
    assert error.existing_owner == "plugin_a"
    assert error.new_owner == "plugin_b"
    assert error.key == "shared"
    message = str(error)
    assert "plugin_a" in message
    assert "plugin_b" in message

    # the original registration is untouched
    assert registry.get("shared") == "value-a"
    assert registry.owner_of("shared") == "plugin_a"


def test_find_with_predicate():
    registry: Registry[int] = Registry("thing")
    registry.register(1, "p", "a")
    registry.register(2, "p", "b")
    registry.register(3, "p", "c")

    assert registry.find(lambda value: value % 2 == 1) == [1, 3]


class _Ordered:
    def __init__(self, label: str, order: int):
        self.label = label
        self.order = order


def test_iteration_is_ordered_by_order_attribute_when_present():
    registry: Registry[_Ordered] = Registry("thing")
    registry.register(_Ordered("c", 300), "p", "c")
    registry.register(_Ordered("a", 100), "p", "a")
    registry.register(_Ordered("b", 200), "p", "b")

    assert [item.label for item in registry] == ["a", "b", "c"]


def test_iteration_without_order_attribute_keeps_insertion_order():
    registry: Registry[str] = Registry("thing")
    registry.register("first", "p", "a")
    registry.register("second", "p", "b")
    registry.register("third", "p", "c")

    assert list(registry) == ["first", "second", "third"]


def test_iteration_mixes_ordered_and_default_zero_order():
    # items without `order` behave as order=0 and come before an
    # explicitly higher order, but keep their relative insertion order
    # among themselves.
    registry: Registry = Registry("thing")
    registry.register("no-order-1", "p", "a")
    registry.register(_Ordered("high", 10), "p", "b")
    registry.register("no-order-2", "p", "c")

    result = list(registry)
    assert result[0] == "no-order-1"
    assert result[1] == "no-order-2"
    assert result[2].label == "high"


def test_remove_owner_removes_only_that_owners_items():
    registry: Registry[str] = Registry("thing")
    registry.register("a1", "pkg_a", "a1")
    registry.register("b1", "pkg_b", "b1")
    registry.register("a2", "pkg_a", "a2")

    removed = registry.remove_owner("pkg_a")

    assert removed == ["a1", "a2"]
    assert registry.keys() == ["b1"]
    assert registry.owner_of("a1") is None
    # keys freed by remove_owner can be registered again
    registry.register("a1-again", "pkg_c", "a1")
    assert registry.owner_of("a1") == "pkg_c"
    assert registry.remove_owner("nobody") == []
