"""Invalidação de cache baseada em padrões."""

import logging
from typing import List

log = logging.getLogger(__name__)


class CacheInvalidator:
    def __init__(self):
        self._patterns: List[str] = []

    def add_pattern(self, prefix: str) -> None:
        self._patterns.append(prefix)
        log.info("Invalidation pattern added: '%s'", prefix)

    def should_invalidate(self, key: str) -> bool:
        for prefix in self._patterns:
            if key.startswith(prefix):
                log.debug("Key '%s' matched invalidation pattern '%s'", key, prefix)
                return True
        return False
