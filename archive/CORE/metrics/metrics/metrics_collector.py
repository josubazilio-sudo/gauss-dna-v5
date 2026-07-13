import logging
from typing import Any, Callable, Dict

log = logging.getLogger(__name__)


class MetricsCollector:
    def __init__(self):
        self._collectors: Dict[str, Callable[[], Any]] = {}

    def register_collector(self, name: str, fn: Callable[[], Any]) -> None:
        self._collectors[name] = fn

    def collect(self, name: str) -> Any:
        fn = self._collectors.get(name)
        if fn:
            return fn()
        return None
