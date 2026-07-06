"""
Valida critérios obrigatórios antes da certificação de Baseline.
"""

from typing import List


class BaselineValidator:
    REQUIRED_CRITERIA = [
        "architecture_approved",
        "tests_passed",
        "quality_gate_passed",
        "audit_completed",
        "documentation_updated",
        "project_dna_updated",
        "changelog_updated",
        "compatibility_validated",
    ]

    def validate(self, artifacts: list) -> List[str]:
        errors = []
        for criterion in self.REQUIRED_CRITERIA:
            if criterion not in artifacts:
                errors.append(f"Criterio ausente: {criterion}")
        return errors
