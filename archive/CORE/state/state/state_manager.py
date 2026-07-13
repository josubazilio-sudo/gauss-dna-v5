"""Coordenador central de estado."""

import logging

from .state_store import StateStore
from .state_machine import StateMachine
from .state_validator import StateValidator
from .state_snapshot import StateSnapshot
from .state_report import StateReport

log = logging.getLogger(__name__)


class StateManager:
    def __init__(self):
        self._store = StateStore()
        self._validator = StateValidator()
        self._machine = StateMachine(self._validator)
        self._snapshot = StateSnapshot()
        self._reporter = StateReport()
        log.info("StateManager initialized")

    def set(self, key: str, value) -> None:
        self._store.set(key, value)
        log.info("State updated: %s", key)

    def get(self, key: str):
        return self._store.get(key)

    def delete(self, key: str) -> None:
        self._store.delete(key)
        log.info("State deleted: %s", key)

    def transition(self, new_state: str) -> bool:
        if self._machine.transition(new_state):
            self._snapshot.record(new_state)
            return True
        log.warning("State transition to '%s' rejected", new_state)
        return False

    def current_state(self) -> str:
        return self._machine.current()

    def get_report(self) -> str:
        return self._reporter.generate(self._store.get_all())
