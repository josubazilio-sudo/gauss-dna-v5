import logging
from typing import Callable

from .event_bus import EventBus
from .events import Event

log = logging.getLogger(__name__)


class Dispatcher:
    def __init__(self, bus: EventBus):
        self._bus = bus

    def dispatch(self, event: Event) -> None:
        self._bus.publish(event)

    def register(self, event_type: str, handler: Callable) -> None:
        self._bus.subscribe(event_type, handler)
