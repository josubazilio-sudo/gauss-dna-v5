import logging
import time
from typing import Dict
from ..events.event_bus import EventBus
from ..events.events import Event
from .health_monitor import HealthMonitor, HealthLevel

log = logging.getLogger(__name__)


class Heartbeat:
    def __init__(self, monitor: HealthMonitor, bus: EventBus):
        self._monitor = monitor
        self._bus = bus
        self._last_beat: Dict[str, float] = {}

    def register(self, module: str) -> None:
        self._last_beat[module] = time.time()
        log.debug("Heartbeat registrado: %s", module)

    def check(self, module: str, timeout: float = 30.0) -> bool:
        last = self._last_beat.get(module, 0)
        if time.time() - last > timeout:
            self._monitor.update_status(module, HealthLevel.WARNING)
            return False
        return True
