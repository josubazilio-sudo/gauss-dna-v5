import logging
from typing import Dict, Any, Optional

log = logging.getLogger(__name__)


class ServiceRegistry:
    def __init__(self, logger=None):
        self._log = logger or log
        self._services: Dict[str, Any] = {}

    def register(self, name: str, instance: Any, metadata: dict = None) -> None:
        self._services[name] = {
            "instance": instance,
            "metadata": metadata or {},
        }
        self._log.info(f"Service registered: {name}")

    def unregister(self, name: str) -> None:
        self._services.pop(name, None)
        self._log.info(f"Service removed: {name}")

    def get(self, name: str) -> Optional[Any]:
        service = self._services.get(name)
        return service["instance"] if service else None

    def exists(self, name: str) -> bool:
        return name in self._services

    def list_all(self) -> Dict[str, Any]:
        return {
            name: info["metadata"]
            for name, info in self._services.items()
        }
