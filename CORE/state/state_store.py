"""Armazenamento de estado em memória."""

import logging
from typing import Dict, Any, Optional

log = logging.getLogger(__name__)


class StateStore:
    def __init__(self):
        self._data: Dict[str, Any] = {}
        log.info("StateStore initialized")

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        log.debug("State stored: %s", key)

    def get(self, key: str) -> Optional[Any]:
        value = self._data.get(key)
        if value is None:
            log.debug("State key not found: %s", key)
        return value

    def delete(self, key: str) -> None:
        if key in self._data:
            del self._data[key]
            log.debug("State deleted: %s", key)
        else:
            log.warning("Attempted to delete unknown state key: %s", key)

    def get_all(self) -> Dict[str, Any]:
        return dict(self._data)

    def clear(self) -> None:
        count = len(self._data)
        self._data.clear()
        log.debug("State store cleared (%d keys)", count)
