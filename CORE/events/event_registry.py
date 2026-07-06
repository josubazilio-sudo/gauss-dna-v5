import logging
from typing import Dict, Optional

log = logging.getLogger(__name__)


class EventRegistry:
    def __init__(self, logger: logging.Logger = None):
        self._events: Dict[str, str] = {}
        self._log = logger or log

    def register(self, event_type: str, description: str) -> None:
        self._events[event_type] = description
        self._log.debug("Registered event type: %s", event_type)

    def is_registered(self, event_type: str) -> bool:
        return event_type in self._events

    def list_events(self) -> Dict[str, str]:
        return dict(self._events)

    def validate(self, event_type: str) -> bool:
        return self.is_registered(event_type)
