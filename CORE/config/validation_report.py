"""
Relatório completo de validação de configurações.
"""

from typing import List, Dict, Any
from datetime import datetime


class ValidationResult:
    def __init__(self):
        self.timestamp = datetime.utcnow()
        self.is_valid = True
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def add_error(self, error: str) -> None:
        self.errors.append(error)
        self.is_valid = False

    def add_warning(self, warning: str) -> None:
        self.warnings.append(warning)


class ValidationReport:
    def __init__(self, result: ValidationResult):
        self._result = result

    def generate(self) -> str:
        lines = [f"Validacao: {self._result.timestamp.isoformat()}"]
        lines.append(f"Resultado: {'VALID' if self._result.is_valid else 'INVALID'}")
        if self._result.errors:
            lines.append(f"\nErros ({len(self._result.errors)}):")
            for e in self._result.errors:
                lines.append(f"  - {e}")
        if self._result.warnings:
            lines.append(f"\nAvisos ({len(self._result.warnings)}):")
            for w in self._result.warnings:
                lines.append(f"  - {w}")
        return "\n".join(lines)
