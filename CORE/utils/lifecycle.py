import logging
from enum import Enum, auto
from typing import Dict, Any, Optional
from ..events.event_bus import EventBus
from ..events.events import Event

log = logging.getLogger(__name__)


class ModuleState(Enum):
    CREATED = auto()
    INITIALIZED = auto()
    VALIDATED = auto()
    READY = auto()
    RUNNING = auto()
    PAUSED = auto()
    RESUMED = auto()
    STOPPING = auto()
    STOPPED = auto()
    RECOVERY = auto()
    FAILED = auto()


TRANSITIONS = {
    ModuleState.CREATED: [ModuleState.INITIALIZED],
    ModuleState.INITIALIZED: [ModuleState.VALIDATED],
    ModuleState.VALIDATED: [ModuleState.READY],
    ModuleState.READY: [ModuleState.RUNNING],
    ModuleState.RUNNING: [ModuleState.PAUSED, ModuleState.STOPPING, ModuleState.FAILED],
    ModuleState.PAUSED: [ModuleState.RESUMED],
    ModuleState.RESUMED: [ModuleState.RUNNING],
    ModuleState.STOPPING: [ModuleState.STOPPED],
    ModuleState.FAILED: [ModuleState.RECOVERY],
    ModuleState.RECOVERY: [ModuleState.READY],
}


class Lifecycle:
    def __init__(self, name: str, bus: Optional[EventBus] = None):
        self._name = name
        self._state = ModuleState.CREATED
        if bus is None:
            bus = EventBus()
        self._bus = bus

    @property
    def state(self) -> ModuleState:
        return self._state

    def transition(self, target: ModuleState) -> bool:
        if target not in TRANSITIONS.get(self._state, []):
            log.error("Transicao invalida: %s -> %s", self._state, target)
            return False
        log.info("Transicao: %s -> %s", self._state, target)
        self._state = target
        self._bus.publish(Event(f"module.{target.name.lower()}", {
            "module": self._name,
            "state": target.name,
        }))
        return True

    def can_transition(self, target: ModuleState) -> bool:
        return target in TRANSITIONS.get(self._state, [])
