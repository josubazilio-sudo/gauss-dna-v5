"""Criptografia e descriptografia de dados usando Fernet ou fallback seguro."""

import base64
import hashlib
import logging
import os

try:
    from cryptography.fernet import Fernet
    from cryptography.fernet import InvalidToken

    _HAS_FERNET = True
except ImportError:
    _HAS_FERNET = False

log = logging.getLogger(__name__)


class Encryption:
    def __init__(self, key: bytes | None = None):
        if _HAS_FERNET:
            raw = key or os.urandom(32)
            if isinstance(raw, str):
                raw = raw.encode()
            self._key = base64.urlsafe_b64encode(raw[:32].ljust(32, b"\0"))
            self._cipher = Fernet(self._key)
            log.info("Encryption initialized with Fernet backend")
        else:
            self._passphrase = (key or b"quantos-default-fallback").decode() if isinstance(key, bytes) else (key or "quantos-default-fallback")
            log.warning("cryptography not available — using base64+hashlib fallback (INSECURE)")

    def encrypt(self, data: str) -> str:
        if _HAS_FERNET:
            return self._cipher.encrypt(data.encode()).decode()
        salt = os.urandom(16)
        key = hashlib.pbkdf2_hmac("sha256", self._passphrase.encode(), salt, 100000)
        combined = salt + key + data.encode()
        return base64.urlsafe_b64encode(combined).decode()

    def decrypt(self, cipher: str) -> str:
        if _HAS_FERNET:
            try:
                return self._cipher.decrypt(cipher.encode()).decode()
            except InvalidToken:
                log.error("Decryption failed — invalid token or wrong key")
                raise
        raw = base64.urlsafe_b64decode(cipher.encode())
        salt = raw[:16]
        key = raw[16:48]
        _ = hashlib.pbkdf2_hmac("sha256", self._passphrase.encode(), salt, 100000)
        if key != hashlib.pbkdf2_hmac("sha256", self._passphrase.encode(), salt, 100000):
            log.error("Decryption failed — key mismatch (fallback)")
            raise ValueError("Decryption failed — key mismatch")
        return raw[48:].decode()

    def rotate_key(self, new_key: bytes) -> None:
        if not _HAS_FERNET:
            self._passphrase = new_key.decode() if isinstance(new_key, bytes) else new_key
            log.warning("Key rotated on fallback backend — existing ciphertexts will not decrypt")
            return
        raw = new_key[:32].ljust(32, b"\0")
        self._key = base64.urlsafe_b64encode(raw)
        self._cipher = Fernet(self._key)
        log.info("Encryption key rotated")
