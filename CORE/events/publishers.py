import logging

from .event_bus import EventBus
from .events import Event, EventTypes

log = logging.getLogger(__name__)


class Publisher:
    def __init__(self, bus: EventBus):
        self._bus = bus

    def system_started(self) -> None:
        self._bus.publish(Event(EventTypes.ENGINE_START, {"status": "started"}))

    def system_stopped(self) -> None:
        self._bus.publish(Event(EventTypes.ENGINE_STOP, {"status": "stopped"}))

    def scan_complete(self, data: dict) -> None:
        self._bus.publish(Event(EventTypes.SCAN_COMPLETE, data))

    def signal_generated(self, data: dict) -> None:
        self._bus.publish(Event(EventTypes.SIGNAL_GENERATED, data))

    def decision_made(self, data: dict) -> None:
        self._bus.publish(Event(EventTypes.DECISION_MADE, data))

    def decision_rejected(self, data: dict) -> None:
        self._bus.publish(Event(EventTypes.DECISION_REJECTED, data))

    def baseline_created(self, data: dict) -> None:
        self._bus.publish(Event(EventTypes.BASELINE_CREATED, data))

    def trade_opened(self, data: dict) -> None:
        self._bus.publish(Event(EventTypes.TRADE_OPENED, data))

    def trade_closed(self, data: dict) -> None:
        self._bus.publish(Event(EventTypes.TRADE_CLOSED, data))

    def error_occurred(self, module: str, error: str) -> None:
        self._bus.publish(Event(EventTypes.ENGINE_ERROR, {
            "module": module, "error": error
        }))
