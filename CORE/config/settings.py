"""
Configurações globais do QuantOS.

Gerencia variáveis de ambiente, parâmetros de trading,
conexões com exchanges e configurações do sistema.
"""

import os
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
            self.mode: str = os.getenv("QUANTOS_MODE", "DEVELOPMENT")
            self.telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
            self.telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")
            self.min_quality_score: float = float(os.getenv("MIN_QUALITY_SCORE", "0.85"))
            self.min_confidence_score: float = float(os.getenv("MIN_CONFIDENCE_SCORE", "0.85"))
            self.max_scan_pairs: int = int(os.getenv("QUANTOS_MAX_SCAN_PAIRS", "300"))
            self.scan_max_workers: int = int(os.getenv("QUANTOS_SCAN_MAX_WORKERS", "10"))
            self.health_alert_threshold: int = int(os.getenv("HEALTH_ALERT_THRESHOLD", "90"))
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


settings = Settings()
