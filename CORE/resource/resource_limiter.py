"""Aplicação de limites de recursos."""

import logging
from typing import Dict

log = logging.getLogger(__name__)


class ResourceLimiter:
    def __init__(self):
        self._limits: Dict[str, float] = {"cpu": 80.0, "memory": 80.0, "disk": 90.0}
        log.info("ResourceLimiter initialized with limits: %s", self._limits)

    def exceeded(self, usage: Dict[str, float]) -> bool:
        for resource, value in usage.items():
            limit = self._limits.get(resource)
            if limit is not None and value > limit:
                log.warning("Resource '%s' at %.1f%% exceeds limit %.1f%%", resource, value, limit)
                return True
        return False

    def set_limit(self, resource: str, value: float) -> None:
        self._limits[resource] = value
        log.info("Limit for '%s' set to %.1f%%", resource, value)
