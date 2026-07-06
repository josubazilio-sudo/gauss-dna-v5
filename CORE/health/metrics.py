import logging
from typing import Dict, Any

log = logging.getLogger(__name__)


class Metrics:
    def __init__(self):
        self._data: Dict[str, Any] = {}

    def record(self, key: str, value: Any) -> None:
        self._data[key] = value
        log.debug("Metric recorded: %s = %s", key, value)

    def increment(self, key: str) -> None:
        self._data[key] = self._data.get(key, 0) + 1
        log.debug("Metric incremented: %s = %s", key, self._data[key])

    def snapshot(self) -> Dict[str, Any]:
        return dict(self._data)
