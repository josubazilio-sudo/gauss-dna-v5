"""Gerenciamento de papéis e grupos."""

import logging
from typing import Dict

log = logging.getLogger(__name__)


class RoleManager:
    def __init__(self):
        self._roles: Dict[str, str] = {}
        log.info("RoleManager initialized")

    def assign(self, user: str, role: str) -> None:
        if not user or not role:
            raise ValueError("User and role must not be empty")
        self._roles[user] = role
        log.info("Role '%s' assigned to user '%s'", role, user)

    def get_role(self, user: str) -> str:
        role = self._roles.get(user, "viewer")
        log.debug("User '%s' has role '%s'", user, role)
        return role

    def list_roles(self) -> Dict[str, str]:
        return dict(self._roles)
