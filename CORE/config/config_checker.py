"""
Verificador de integridade e consistência das configurações.
"""

from typing import Dict, Any, List
from ..logger.logger import Logger


class ConfigChecker:
    def __init__(self):
        self._log = Logger().get_logger("config.checker")

    def check_integrity(self, config: Dict[str, Any]) -> List[str]:
        issues = []
        for key, value in config.items():
            if value is None:
                issues.append(f"Configuracao nula: {key}")
        return issues

    def check_consistency(self, config: Dict[str, Any]) -> List[str]:
        issues = []
        if config.get("debug") and config.get("environment") == "production":
            issues.append("Modo debug ativo em producao")
        return issues
