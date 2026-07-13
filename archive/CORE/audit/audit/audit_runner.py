import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from .audit_rules import AuditRules

log = logging.getLogger(__name__)


class AuditRunner:
    def execute(
        self, scope: str, target: Dict[str, Any], rules: AuditRules
    ) -> Dict[str, Any]:
        violations: List[str] = []
        any_critical_failed = False

        for rule in rules.get_for_scope(scope):
            if rule.check(target):
                violations.append(rule.describe())
                if rule.is_critical:
                    any_critical_failed = True

        if any_critical_failed:
            status = "REPROVADO"
        elif violations:
            status = "APROVADO_COM_RESSALVAS"
        else:
            status = "APROVADO"

        log.info(
            "Auditoria [%s] concluída: %d violações, status=%s",
            scope, len(violations), status,
        )

        return {
            "status": status,
            "violations": violations,
            "scope": scope,
            "executed_at": datetime.now(timezone.utc).isoformat(),
        }
