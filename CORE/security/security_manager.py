"""Coordenador central de segurança."""

import logging

from .encryption import Encryption
from .token_manager import TokenManager
from .key_vault import KeyVault
from .secret_manager import SecretManager
from .security_audit import SecurityAudit

log = logging.getLogger(__name__)


class SecurityManager:
    def __init__(self):
        self._encryption = Encryption()
        self._tokens = TokenManager()
        self._vault = KeyVault()
        self._secrets = SecretManager()
        self._audit = SecurityAudit()
        log.info("SecurityManager initialized")

    def encrypt(self, data: str) -> str:
        result = self._encryption.encrypt(data)
        self._audit.log("encrypt", "data encrypted")
        log.debug("Encrypt operation completed")
        return result

    def decrypt(self, cipher: str) -> str:
        result = self._encryption.decrypt(cipher)
        self._audit.log("decrypt", "data decrypted")
        log.debug("Decrypt operation completed")
        return result

    def validate_token(self, token: str) -> bool:
        return self._tokens.validate(token)

    def create_token(self, user: str) -> str:
        token = self._tokens.create(user)
        self._audit.log("token_create", f"token created for {user}")
        return token

    def revoke_token(self, token: str) -> None:
        self._tokens.revoke(token)
        self._audit.log("token_revoke", "token revoked")
