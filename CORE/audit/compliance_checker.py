import logging
from typing import Any, Dict, List

log = logging.getLogger(__name__)


class ComplianceChecker:
    def check(self, target: Dict[str, Any], required_docs: List[str]) -> List[str]:
        missing: List[str] = []
        for doc in required_docs:
            if doc not in target.get("documents", []):
                missing.append(f"Documento ausente: {doc}")
        return missing
