import logging
from datetime import datetime, timezone
from typing import Dict, Any

log = logging.getLogger(__name__)


class BaselineManager:
    def __init__(self):
        self._log = log
        self._baselines: Dict[str, Dict[str, Any]] = {}

    def create(self, module: str, version: str) -> None:
        baseline = {
            "module": module,
            "version": version,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "active",
        }
        self._baselines[f"{module}@{version}"] = baseline
        self._log.info(f"Baseline: {module}@{version}")

    def get(self, module: str, version: str) -> Dict[str, Any]:
        return self._baselines.get(f"{module}@{version}", {})

    def list_all(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._baselines)
