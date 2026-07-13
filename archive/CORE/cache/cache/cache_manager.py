"""Coordenador central de cache."""

import logging

from .cache_store import CacheStore
from .cache_policy import CachePolicy
from .cache_invalidator import CacheInvalidator
from .cache_stats import CacheStats
from .cache_report import CacheReport

log = logging.getLogger(__name__)


class CacheManager:
    def __init__(self):
        self._store = CacheStore()
        self._policy = CachePolicy()
        self._invalidator = CacheInvalidator()
        self._stats = CacheStats()
        self._reporter = CacheReport()
        log.info("CacheManager initialized")

    def get(self, key: str):
        value = self._store.get(key)
        if value is not None:
            self._stats.hit(key)
        else:
            self._stats.miss(key)
        return value

    def set(self, key: str, value, ttl: int = 300) -> None:
        if not self._policy.allowed(key):
            log.debug("Cache set blocked by policy: %s", key)
            return
        self._store.set(key, value, ttl)
        log.info("Cache set: %s (ttl=%ds)", key, ttl)

    def delete(self, key: str) -> None:
        self._store.delete(key)
        log.debug("Cache deleted: %s", key)

    def clear(self) -> None:
        self._store.clear()

    def get_report(self) -> str:
        return self._reporter.generate(self._stats)
