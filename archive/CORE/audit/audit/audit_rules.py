import logging
from typing import Dict, List

log = logging.getLogger(__name__)


class AuditRule:
    def __init__(self, name: str, scope: str, is_critical: bool = False) -> None:
        self.name = name
        self.scope = scope
        self.is_critical = is_critical

    def check(self, target: Dict) -> bool:
        raise NotImplementedError

    def describe(self) -> str:
        raise NotImplementedError


class AuditRules:
    def __init__(self) -> None:
        self._rules: List[AuditRule] = []

    def add_rule(self, rule: AuditRule) -> None:
        self._rules.append(rule)

    def get_for_scope(self, scope: str) -> List[AuditRule]:
        return [r for r in self._rules if r.scope == scope]
