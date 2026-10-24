"""
------------------------------------------------------------------------
File : event_bus.py
Description: EventBus (Observer, scheda C6) - lets packages react to
             each other and to the core's lifecycle events
             (soup/core/events.py) without depending on each other's
             code. Handlers run synchronously, in subscription order,
             each receiving a read-only view of the payload. A failing
             handler is logged and does not stop the others, unless it
             subscribed as critical: then the error propagates to the
             publisher and the remaining handlers are not called.
             Copy-on-write: subscribe/remove_owner build a new mapping and
             publish it with one assignment under a lock; publish() reads
             the current snapshot without locking, so packages can be
             installed or disabled while events are being published.
Project : soup-server
------------------------------------------------------------------------
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Optional

from soup.core.contracts import EventHandler

_LOGGER = logging.getLogger("soup.events")


@dataclass(frozen=True)
class Subscription:
    event: str
    handler: EventHandler
    owner: str
    critical: bool = False


class EventBus:
    def __init__(self, logger: Optional[logging.Logger] = None):
        self._logger = logger or _LOGGER
        # Never mutated: replaced as a whole on every change.
        self._subscriptions: Mapping[str, tuple[Subscription, ...]] = MappingProxyType({})
        self._lock = threading.Lock()

    def subscribe(self, event: str, handler: EventHandler, owner: str, critical: bool = False) -> None:
        if not isinstance(event, str) or not event:
            raise ValueError("Event name must be a non-empty string")
        if not callable(handler):
            raise ValueError(f"Handler for event '{event}' must be callable")
        subscription = Subscription(event, handler, owner, critical)
        with self._lock:
            current = self._subscriptions
            self._subscriptions = MappingProxyType({**current, event: (*current.get(event, ()), subscription)})

    def remove_owner(self, owner: str) -> None:
        with self._lock:
            kept = {
                event: tuple(subscription for subscription in subscriptions if subscription.owner != owner)
                for event, subscriptions in self._subscriptions.items()
            }
            self._subscriptions = MappingProxyType({event: subs for event, subs in kept.items() if subs})

    def subscribers(self, event: str) -> list[Subscription]:
        return list(self._subscriptions.get(event, ()))

    def publish(self, event: str, payload: Optional[Mapping[str, Any]] = None) -> None:
        view = MappingProxyType(dict(payload or {}))
        for subscription in self.subscribers(event):
            try:
                subscription.handler(view)
            except Exception:
                if subscription.critical:
                    raise
                self._logger.exception(
                    "Handler of package '%s' for event '%s' failed", subscription.owner, event
                )
