"""Armazenamento de dados em cache com suporte a TTL."""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta, timezone

log = logging.getLogger(__name__)


class CacheEntry:
    def __init__(self, value: Any, ttl: int):
        self.value = value
        self.expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl)

    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at


class CacheStore:
    def __init__(self):
        self._data: Dict[str, CacheEntry] = {}
        log.info("CacheStore initialized")

    def set(self, key: str, value: Any, ttl: int) -> None:
        self._data[key] = CacheEntry(value, ttl)
        log.debug("Cache set: %s (ttl=%ds)", key, ttl)

    def get(self, key: str) -> Optional[Any]:
        entry = self._data.get(key)
        if not entry:
            log.debug("Cache miss: %s (not found)", key)
            return None
        if entry.is_expired():
            del self._data[key]
            log.debug("Cache miss: %s (expired)", key)
            return None
        log.debug("Cache hit: %s", key)
        return entry.value

    def delete(self, key: str) -> None:
        if key in self._data:
            del self._data[key]
            log.debug("Cache deleted: %s", key)

    def clear(self) -> None:
        count = len(self._data)
        self._data.clear()
        log.debug("Cache cleared (%d entries)", count)

    def size(self) -> int:
        return len(self._data)
