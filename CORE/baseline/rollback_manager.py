import logging
from typing import Dict, Any

log = logging.getLogger(__name__)


class RollbackManager:
    def __init__(self):
        self._log = log
        self._history: list = []

    def execute(self, baseline: Dict[str, Any]) -> bool:
        name = baseline.get("name", "unknown")
        version = baseline.get("version", "unknown")
        self._history.append({
            "action": "rollback",
            "name": name,
            "version": version,
        })
        self._log.info(f"Rollback executado: {name}@{version}")
        return True

    def history(self) -> list:
        return list(self._history)
