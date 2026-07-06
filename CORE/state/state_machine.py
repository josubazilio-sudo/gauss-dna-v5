"""Máquina de estados com validação de transições."""

import logging
from typing import Optional

from .state_validator import StateValidator

log = logging.getLogger(__name__)


class StateMachine:
    def __init__(self, validator: Optional[StateValidator] = None):
        self._current = "init"
        self._validator = validator or StateValidator()
        log.info("StateMachine initialized at '%s'", self._current)

    def current(self) -> str:
        return self._current

    def transition(self, new_state: str) -> bool:
        if not self._validator.can_transition(self._current, new_state):
            log.warning(
                "Invalid transition: '%s' -> '%s' not allowed",
                self._current,
                new_state,
            )
            return False
        old = self._current
        self._current = new_state
        log.info("State transition: '%s' -> '%s'", old, new_state)
        return True

    def can_transition(self, target: str) -> bool:
        return self._validator.can_transition(self._current, target)

    def reset(self) -> None:
        self._current = "init"
        log.info("StateMachine reset to 'init'")
