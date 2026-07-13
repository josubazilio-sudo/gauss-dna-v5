"""Validador de transições de estado."""

import logging
from typing import Dict, List

log = logging.getLogger(__name__)


class StateValidator:
    VALID_TRANSITIONS: Dict[str, List[str]] = {
        "init": ["booting", "error"],
        "booting": ["running", "error"],
        "running": ["paused", "stopped", "error"],
        "paused": ["running", "stopped"],
        "stopped": ["init"],
        "error": ["init"],
    }

    def can_transition(self, current: str, target: str) -> bool:
        allowed = self.VALID_TRANSITIONS.get(current, [])
        if target in allowed:
            log.debug("Transition '%s' -> '%s' allowed", current, target)
            return True
        log.warning("Transition '%s' -> '%s' not allowed", current, target)
        return False

    def add_transition(self, current: str, target: str) -> None:
        if current not in self.VALID_TRANSITIONS:
            self.VALID_TRANSITIONS[current] = []
        if target not in self.VALID_TRANSITIONS[current]:
            self.VALID_TRANSITIONS[current].append(target)
            log.info("Transition added: '%s' -> '%s'", current, target)
