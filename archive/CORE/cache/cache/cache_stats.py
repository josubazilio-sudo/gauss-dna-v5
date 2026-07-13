"""Estatísticas de cache."""

import logging
from typing import Dict

log = logging.getLogger(__name__)


class CacheStats:
    def __init__(self):
        self._hits = 0
        self._misses = 0

    def hit(self, key: str) -> None:
        self._hits += 1
        log.debug("Stat hit: %s (total hits=%d)", key, self._hits)

    def miss(self, key: str) -> None:
        self._misses += 1
        log.debug("Stat miss: %s (total misses=%d)", key, self._misses)

    def get_ratio(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    def get_stats(self) -> Dict[str, int]:
        return {"hits": self._hits, "misses": self._misses}
