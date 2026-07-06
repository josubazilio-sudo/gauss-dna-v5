import logging
from typing import Any, Dict, List

log = logging.getLogger(__name__)


class CodeQualityChecker:
    def check(self, target: Dict[str, Any]) -> List[str]:
        issues: List[str] = []
        if target.get("duplicated_code"):
            issues.append("Codigo duplicado detectado")
        if target.get("missing_tests"):
            issues.append("Testes obrigatorios ausentes")
        if target.get("missing_docs"):
            issues.append("Documentacao ausente")
        return issues
