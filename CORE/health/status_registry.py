import logging
from typing import Dict, Any
from .health_monitor import HealthLevel

log = logging.getLogger(__name__)


class StatusRegistry:
    def __init__(self):
        self._registry: Dict[str, Dict[str, Any]] = {}

    def register(self, module: str, metadata: Dict[str, Any]) -> None:
        self._registry[module] = {
            "metadata": metadata,
            "status": HealthLevel.HEALTHY.value,
        }

    def update(self, module: str, status: str) -> None:
        if module in self._registry:
            self._registry[module]["status"] = status

    def get_all(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._registry)

    def get(self, module: str) -> Dict[str, Any]:
        return self._registry.get(module, {})
