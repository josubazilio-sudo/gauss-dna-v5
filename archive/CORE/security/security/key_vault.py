"""Armazenamento seguro de chaves em memória."""

import logging
from typing import Dict, Optional

log = logging.getLogger(__name__)


class KeyVault:
    def __init__(self):
        self._keys: Dict[str, str] = {}
        log.info("KeyVault initialized (in-memory)")

    def store(self, name: str, key: str) -> None:
        if not name:
            raise ValueError("Key name cannot be empty")
        self._keys[name] = key
        log.info("Key '%s' stored", name)

    def retrieve(self, name: str) -> Optional[str]:
        value = self._keys.get(name)
        if value is None:
            log.warning("Key '%s' not found", name)
        return value

    def delete(self, name: str) -> None:
        if name in self._keys:
            del self._keys[name]
            log.info("Key '%s' deleted", name)
        else:
            log.warning("Attempted to delete unknown key '%s'", name)
