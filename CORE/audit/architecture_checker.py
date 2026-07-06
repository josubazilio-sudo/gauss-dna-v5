import logging
from typing import Any, Dict, List

log = logging.getLogger(__name__)


class ArchitectureChecker:
    CRITICAL_VIOLATIONS: List[str] = [
        "circular_dependency",
        "missing_interface",
        "direct_module_access",
        "baseline_violation",
    ]

    def check(self, target: Dict[str, Any]) -> List[str]:
        violations: List[str] = []
        for v in self.CRITICAL_VIOLATIONS:
            if target.get(v):
                violations.append(v)
        return violations
