"""Registro de permissões disponíveis."""

import logging
from typing import List

log = logging.getLogger(__name__)


class PermissionRegistry:
    def __init__(self):
        self._permissions: List[str] = []
        log.info("PermissionRegistry initialized")

    def register(self, name: str) -> None:
        if not name:
            raise ValueError("Permission name cannot be empty")
        if name not in self._permissions:
            self._permissions.append(name)
            log.info("Permission '%s' registered", name)
        else:
            log.warning("Permission '%s' already registered", name)

    def exists(self, name: str) -> bool:
        return name in self._permissions

    def list_all(self) -> List[str]:
        return list(self._permissions)
