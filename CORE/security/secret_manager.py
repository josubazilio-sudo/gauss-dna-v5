"""Gerenciamento de segredos e credenciais em memória."""

import logging
from typing import Dict, Optional

log = logging.getLogger(__name__)


class SecretManager:
    def __init__(self):
        self._secrets: Dict[str, str] = {}
        log.info("SecretManager initialized (in-memory)")

    def set(self, name: str, value: str) -> None:
        if not name:
            raise ValueError("Secret name cannot be empty")
        self._secrets[name] = value
        log.info("Secret '%s' stored", name)

    def get(self, name: str) -> Optional[str]:
        value = self._secrets.get(name)
        if value is None:
            log.warning("Secret '%s' not found", name)
        return value

    def delete(self, name: str) -> None:
        if name in self._secrets:
            del self._secrets[name]
            log.info("Secret '%s' deleted", name)
        else:
            log.warning("Attempted to delete unknown secret '%s'", name)
