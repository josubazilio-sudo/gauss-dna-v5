"""Coordenador central de permissões."""

import logging

from .permission_registry import PermissionRegistry
from .access_control import AccessControl
from .role_manager import RoleManager
from .policy_engine import PolicyEngine
from .permission_audit import PermissionAudit

log = logging.getLogger(__name__)


class PermissionManager:
    def __init__(self):
        self._registry = PermissionRegistry()
        self._access = AccessControl()
        self._roles = RoleManager()
        self._policies = PolicyEngine()
        self._audit = PermissionAudit()
        log.info("PermissionManager initialized")

    def authorize(self, user: str, action: str, resource: str) -> bool:
        role = self._roles.get_role(user)
        if self._policies.evaluate(role, action, resource):
            self._audit.log("authorized", f"{user} -> {action} on {resource}")
            log.info("Authorized: %s %s on %s", user, action, resource)
            return True
        self._audit.log("denied", f"{user} -> {action} on {resource}")
        log.warning("Denied: %s %s on %s", user, action, resource)
        return False
