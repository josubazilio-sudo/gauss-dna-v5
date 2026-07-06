"""Gerenciamento de tokens de acesso com secrets token_hex."""

import logging
import secrets
from typing import Dict, Optional

log = logging.getLogger(__name__)


class TokenManager:
    def __init__(self):
        self._tokens: Dict[str, str] = {}

    def create(self, user: str) -> str:
        token = secrets.token_hex(32)
        self._tokens[token] = user
        log.info("Token created for user '%s'", user)
        return token

    def validate(self, token: str) -> bool:
        valid = token in self._tokens
        if not valid:
            log.warning("Token validation failed — token not found")
        return valid

    def revoke(self, token: str) -> None:
        user = self._tokens.pop(token, None)
        if user:
            log.info("Token revoked for user '%s'", user)
        else:
            log.warning("Attempted to revoke unknown token")

    def get_user(self, token: str) -> Optional[str]:
        return self._tokens.get(token)
