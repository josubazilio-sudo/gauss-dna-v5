import logging
from typing import List
from .service_registry import ServiceRegistry

log = logging.getLogger(__name__)


class ServiceValidator:
    def __init__(self):
        self._errors: List[str] = []

    def validate(self, registry: ServiceRegistry) -> bool:
        self._errors.clear()
        for name in registry.list_all():
            if registry.get(name) is None:
                self._errors.append(f"Service without instance: {name}")
        result = len(self._errors) == 0
        log.info(f"Service validation {'passed' if result else 'failed'} ({len(self._errors)} errors)")
        return result

    def get_errors(self) -> List[str]:
        return self._errors
