import logging
from typing import Dict, Callable, List

from .events import Event

log = logging.getLogger(__name__)


class EventBus:
    def __init__(self, logger: logging.Logger = None):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._log = logger or log

    def subscribe(self, event_type: str, callback: Callable) -> None:
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable) -> None:
        if event_type in self._subscribers:
            self._subscribers[event_type].remove(callback)

    def publish(self, event: Event) -> None:
        for callback in self._subscribers.get(event.type, []):
            try:
                callback(event)
            except Exception:
                self._log.exception(
                    "Subscriber failed for event %s: %s",
                    event.type, callback.__name__,
                )
