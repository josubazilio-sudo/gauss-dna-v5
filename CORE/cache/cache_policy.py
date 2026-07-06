"""Definição de políticas de cache."""

import logging
from typing import Set

log = logging.getLogger(__name__)


class CachePolicy:
    def __init__(self):
        self._blocklist: Set[str] = set()

    def block(self, key: str) -> None:
        self._blocklist.add(key)
        log.info("Cache key blocked: %s", key)

    def unblock(self, key: str) -> None:
        self._blocklist.discard(key)
        log.info("Cache key unblocked: %s", key)

    def allowed(self, key: str) -> bool:
        allowed = key not in self._blocklist
        if not allowed:
            log.debug("Cache key blocked by policy: %s", key)
        return allowed
