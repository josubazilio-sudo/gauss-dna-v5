import hashlib
import hmac
import logging
import time
from typing import Optional

from ..bot_config import BotConfig

log = logging.getLogger(__name__)


class AuthenticationManager:
    def __init__(self, config: BotConfig):
        self._config = config
        self._api_key = config.mexc_api_key
        self._api_secret = config.mexc_api_secret
        self._authenticated = False

    @property
    def authenticated(self) -> bool:
        return self._authenticated

    @property
    def api_key(self) -> str:
        return self._api_key

    def authenticate(self, api_key: str, api_secret: str) -> bool:
        self._api_key = api_key
        self._api_secret = api_secret
        self._authenticated = bool(api_key and api_secret)
        if self._authenticated:
            log.info("AuthenticationManager: authenticated")
        else:
            log.warning("AuthenticationManager: invalid credentials")
        return self._authenticated

    def sign_request(self, params: dict) -> dict:
        query_string = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        signature = hmac.new(
            self._api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        params["signature"] = signature
        return params

    def generate_headers(self) -> dict:
        return {
            "X-MEXC-APIKEY": self._api_key,
            "Content-Type": "application/json",
        }

    def get_timestamp(self) -> int:
        return int(time.time() * 1000)

    def clear(self) -> None:
        self._api_key = ""
        self._api_secret = ""
        self._authenticated = False
        log.info("AuthenticationManager: cleared")
