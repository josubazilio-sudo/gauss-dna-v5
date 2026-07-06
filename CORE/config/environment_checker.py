"""
Validador do ambiente de execução.
"""

from typing import List, Dict, Any
from ..logger.logger import Logger


class EnvironmentChecker:
    def __init__(self):
        self._log = Logger().get_logger("config.environment")

    def check(self, env: Dict[str, Any]) -> List[str]:
        issues = []
        required_vars = ["QUANTOS_ENV"]
        for var in required_vars:
            if var not in env:
                issues.append(f"Variavel de ambiente ausente: {var}")
        return issues
