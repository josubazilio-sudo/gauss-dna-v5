"""
Configurações globais do QuantOS.

Gerencia variáveis de ambiente, parâmetros de trading,
conexões com exchanges e configurações do sistema.
"""

from pathlib import Path
from typing import Dict, Any
from .environment import Environment
from .constants import Constants


class Settings:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            self.env = Environment()
            self.constants = Constants()
            self._config: Dict[str, Any] = {}
            self._config['PRODUCTION_VALIDATION'] = True
            self._initialized = True

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._config[key] = value

    def load_from_file(self, path: Path) -> None:
        if not path.exists():
            return
        with open(path) as f:
            import json
            data = json.load(f)
            self._config.update(data)
