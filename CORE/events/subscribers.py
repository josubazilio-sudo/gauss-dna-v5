import logging
from typing import Callable, Dict, List

from .event_bus import EventBus

log = logging.getLogger(__name__)


class SubscriberGroup:
    def __init__(self, bus: EventBus):
        self._bus = bus
        self._subscriptions: Dict[str, List[Callable]] = {}

    def subscribe(self, event_type: str, callback: Callable) -> None:
        if event_type not in self._subscriptions:
            self._subscriptions[event_type] = []
        self._subscriptions[event_type].append(callback)
        self._bus.subscribe(event_type, callback)
        log.debug("Subscribed %s to %s", callback.__name__, event_type)

    def unsubscribe(self, event_type: str, callback: Callable) -> None:
        if event_type in self._subscriptions:
            self._subscriptions[event_type].remove(callback)
            self._bus.unsubscribe(event_type, callback)
            log.debug("Unsubscribed %s from %s", callback.__name__, event_type)
