"""Minimal in-process publish/subscribe event bus.

Decouples the vision producer from consumers (sound engine, visualizer). This is
the 'in-process messaging' that replaces the original design's TCP socket — and
why the single-client server limitation no longer exists. See spec section 2.
"""
from __future__ import annotations

import threading
from collections import defaultdict
from typing import Callable, DefaultDict, List, Type


class EventBus:
    def __init__(self) -> None:
        self._subscribers: DefaultDict[type, List[Callable]] = defaultdict(list)
        self._lock = threading.Lock()

    def subscribe(self, event_type: Type, handler: Callable) -> None:
        """Register `handler` to receive every event whose type is `event_type`."""
        with self._lock:
            self._subscribers[event_type].append(handler)

    def publish(self, event: object) -> None:
        """Synchronously deliver `event` to all subscribers registered for its type."""
        with self._lock:
            handlers = list(self._subscribers[type(event)])
        for handler in handlers:
            handler(event)
