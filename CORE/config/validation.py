"""
Validação de configurações.

Verifica valores obrigatórios, tipos, duplicações e conflitos
antes da inicialização do sistema.
"""

from typing import Dict, Any, List


class ConfigValidator:
    def __init__(self, config: Dict[str, Any]):
        self._config = config
        self._errors: List[str] = []

    def validate(self) -> bool:
        self._errors.clear()
        self._check_required()
        self._check_types()
        self._check_conflicts()
        return len(self._errors) == 0

    def _check_required(self) -> None:
        required = ["project_name", "version", "environment"]
        for key in required:
            if key not in self._config:
                self._errors.append(f"Configuracao obrigatoria ausente: {key}")

    def _check_types(self) -> None:
        for key, value in self._config.items():
            if key == "debug" and not isinstance(value, bool):
                self._errors.append(f"Tipo invalido para {key}: esperado bool")

    def _check_conflicts(self) -> None:
        if self._config.get("debug") and self._config.get("environment") == "production":
            self._errors.append("Modo debug ativo em ambiente de producao")

    def get_errors(self) -> List[str]:
        return self._errors
