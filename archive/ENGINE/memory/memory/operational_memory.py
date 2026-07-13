import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)


class OperationalMemory:
    def __init__(self, max_entries: int = 1000):
        self._store: Dict[str, Any] = {}
        self._timestamps: Dict[str, datetime] = {}
        self._max_entries = max_entries

    def set(self, key: str, value: Any) -> None:
        if len(self._store) >= self._max_entries:
            oldest = min(self._timestamps, key=lambda k: self._timestamps[k])
            self._store.pop(oldest, None)
            self._timestamps.pop(oldest, None)
        self._store[key] = value
        self._timestamps[key] = datetime.now(timezone.utc)

    def get(self, key: str, default: Any = None) -> Any:
        return self._store.get(key, default)

    def get_with_timestamp(self, key: str) -> Optional[tuple]:
        value = self._store.get(key)
        ts = self._timestamps.get(key)
        if value is not None and ts is not None:
            return value, ts
        return None

    def exists(self, key: str) -> bool:
        return key in self._store

    def remove(self, key: str) -> None:
        self._store.pop(key, None)
        self._timestamps.pop(key, None)

    def clear(self) -> None:
        self._store.clear()
        self._timestamps.clear()

    def keys(self) -> list:
        return list(self._store.keys())

    def snapshot(self) -> Dict[str, Any]:
        return dict(self._store)

    @property
    def size(self) -> int:
        return len(self._store)
