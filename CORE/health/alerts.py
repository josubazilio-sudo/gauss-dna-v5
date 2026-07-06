import logging
from ..events.event_bus import EventBus
from ..events.events import Event

log = logging.getLogger(__name__)


class Alerts:
    def __init__(self, bus: EventBus):
        self._bus = bus

    def emit(self, severity: str, module: str, message: str) -> None:
        log.warning("[%s] %s: %s", severity, module, message)
        self._bus.publish(Event("alert.emitted", {
            "severity": severity,
            "module": module,
            "message": message,
        }))
