"""Controle de acesso a recursos baseado em regras."""

import logging
from typing import List, Tuple

log = logging.getLogger(__name__)


class AccessControl:
    def __init__(self):
        self._rules: List[Tuple[str, str, str]] = []
        log.info("AccessControl initialized")

    def add_rule(self, role: str, resource: str, action: str) -> None:
        self._rules.append((role, resource, action))
        log.info("ACL rule added: %s can %s on %s", role, action, resource)

    def check(self, role: str, resource: str, action: str) -> bool:
        result = (role, resource, action) in self._rules
        log.debug("ACL check: role=%s resource=%s action=%s -> %s", role, resource, action, result)
        return result
