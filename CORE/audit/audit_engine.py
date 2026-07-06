import logging
from .audit_runner import AuditRunner
from .audit_rules import AuditRules
from .audit_registry import AuditRegistry
from .report_generator import ReportGenerator

log = logging.getLogger(__name__)


class AuditEngine:
    def __init__(self):
        self._runner = AuditRunner()
        self._rules = AuditRules()
        self._registry = AuditRegistry()
        self._reporter = ReportGenerator()

    def run_audit(self, scope: str, target: dict) -> str:
        audit_id = self._registry.create_id()
        log.info(f"Auditoria iniciada: {audit_id} | escopo: {scope}")
        results = self._runner.execute(scope, target, self._rules)
        report = self._reporter.generate(audit_id, scope, results)
        self._registry.register(audit_id, scope, results["status"])
        log.info(f"Auditoria concluida: {audit_id} -> {results['status']}")
        return report
