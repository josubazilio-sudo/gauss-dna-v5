import logging
from typing import Optional, Any
from .service_registry import ServiceRegistry

log = logging.getLogger(__name__)


class ServiceLocator:
    def __init__(self, registry: ServiceRegistry):
        self._registry = registry

    def locate(self, name: str) -> Optional[Any]:
        instance = self._registry.get(name)
        if instance is None:
            log.warning(f"Service not found: {name}")
        return instance

    def available(self, name: str) -> bool:
        return self._registry.exists(name)
