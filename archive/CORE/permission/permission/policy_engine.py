"""Avaliação de políticas de acesso."""

import logging
from typing import Set, Tuple

log = logging.getLogger(__name__)


class PolicyEngine:
    def __init__(self):
        self._rules: Set[Tuple[str, str, str]] = {
            ("admin", "*", "*"),
            ("operator", "read", "*"),
            ("operator", "execute", "*"),
            ("viewer", "read", "*"),
        }

    def evaluate(self, role: str, action: str, resource: str) -> bool:
        if (role, "*", "*") in self._rules:
            return True
        if (role, action, "*") in self._rules:
            return True
        if (role, action, resource) in self._rules:
            return True
        log.debug("Policy denied: role=%s action=%s resource=%s", role, action, resource)
        return False

    def add_rule(self, role: str, action: str, resource: str) -> None:
        self._rules.add((role, action, resource))
        log.info("Policy rule added: role=%s action=%s resource=%s", role, action, resource)
