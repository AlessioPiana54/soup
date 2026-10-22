"""
------------------------------------------------------------------------
File : test_event_bus.py
Description: Tests for the EventBus and its PluginContext facade:
             delivery order, isolation of failing handlers, critical
             subscriptions propagating, read-only payloads, removal of a
             failed package's subscriptions.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import pytest

from soup.core.event_bus import EventBus
from soup.core.plugin_context import DefaultPluginContext
from soup.core.plugin_manager import PluginManager
from tests.mediator_doubles import FeaturePackage

# Declared by the (fake) publishing package, as a real one would in its api.py.
EKG_BUILT = "test_publisher.ekg_built"


def test_handlers_receive_events_in_subscription_order():
    bus = EventBus()
    received = []
    bus.subscribe(EKG_BUILT, lambda p: received.append(("first", p["id"])), owner="a")
    bus.subscribe(EKG_BUILT, lambda p: received.append(("second", p["id"])), owner="b")
    bus.subscribe("other.event", lambda p: received.append(("other", p)), owner="c")

    bus.publish(EKG_BUILT, {"id": "orders"})

    assert received == [("first", "orders"), ("second", "orders")]


def test_failing_handler_is_logged_and_does_not_block_the_others(caplog):
    bus = EventBus()
    received = []

    def _broken(payload):
        raise RuntimeError("handler bug")

    bus.subscribe(EKG_BUILT, _broken, owner="buggy")
    bus.subscribe(EKG_BUILT, lambda p: received.append(p["id"]), owner="good")

    bus.publish(EKG_BUILT, {"id": "orders"})

    assert received == ["orders"]
    assert "buggy" in caplog.text and EKG_BUILT in caplog.text


def test_critical_handler_error_propagates_to_the_publisher():
    bus = EventBus()
    received = []

    def _must_succeed(payload):
        raise ValueError("cannot index")

    bus.subscribe(EKG_BUILT, _must_succeed, owner="indexer", critical=True)
    bus.subscribe(EKG_BUILT, lambda p: received.append(p), owner="late")

    with pytest.raises(ValueError, match="cannot index"):
        bus.publish(EKG_BUILT, {"id": "orders"})
    assert received == []


def test_payload_is_read_only():
    bus = EventBus()
    seen = []

    def _mutate(payload):
        payload["id"] = "hacked"

    bus.subscribe(EKG_BUILT, _mutate, owner="a")
    bus.subscribe(EKG_BUILT, lambda p: seen.append(p["id"]), owner="b")

    bus.publish(EKG_BUILT, {"id": "orders"})

    assert seen == ["orders"]


def test_packages_subscribe_and_publish_through_the_context():
    received = []
    ctx = DefaultPluginContext()
    listener = FeaturePackage(
        "listener", on_register=lambda c: c.subscribe(EKG_BUILT, lambda p: received.append(p["id"]))
    )
    publisher = FeaturePackage(
        "publisher", requires=("listener",), on_register=lambda c: c.publish(EKG_BUILT, {"id": "x"})
    )

    report = PluginManager().load([publisher, listener], ctx=ctx)

    assert report.failed == []
    assert received == ["x"]
    assert [s.owner for s in ctx.event_bus.subscribers(EKG_BUILT)] == ["listener"]
    ctx.publish(EKG_BUILT, {"id": "y"})  # at runtime, outside register()
    assert received == ["x", "y"]


def test_subscriptions_of_a_failed_package_are_removed():
    received = []

    def _subscribe_then_fail(ctx):
        ctx.subscribe(EKG_BUILT, lambda p: received.append(p))
        raise RuntimeError("boom")

    ctx = DefaultPluginContext()
    PluginManager().load([FeaturePackage("bad", on_register=_subscribe_then_fail)], ctx=ctx)
    ctx.publish(EKG_BUILT, {"id": "x"})

    assert received == []


def test_event_name_and_handler_are_checked():
    bus = EventBus()
    with pytest.raises(ValueError):
        bus.subscribe("", lambda p: None, owner="a")
    with pytest.raises(ValueError):
        bus.subscribe(EKG_BUILT, "not callable", owner="a")  # type: ignore[arg-type]
