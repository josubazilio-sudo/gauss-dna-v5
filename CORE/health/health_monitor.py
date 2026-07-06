import logging
from enum import Enum
from typing import Dict, Any, Optional
from ..events.event_bus import EventBus
from ..events.events import Event

log = logging.getLogger(__name__)


class HealthLevel(Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    OFFLINE = "offline"


class HealthMonitor:
    def __init__(self, bus: Optional[EventBus] = None):
        if bus is None:
            bus = EventBus()
        self._bus = bus
        self._statuses: Dict[str, HealthLevel] = {}

    def update_status(self, module: str, level: HealthLevel) -> None:
        self._statuses[module] = level
        log.info("Saude [%s]: %s", module, level.value)
        self._bus.publish(Event("health.changed", {
            "module": module,
            "level": level.value,
        }))
        if level in (HealthLevel.CRITICAL, HealthLevel.OFFLINE):
            log.critical("Modulo %s em estado %s", module, level.value)

    def get_status(self, module: str) -> HealthLevel:
        return self._statuses.get(module, HealthLevel.OFFLINE)

    def all_healthy(self) -> bool:
        return all(
            s == HealthLevel.HEALTHY for s in self._statuses.values()
        )
