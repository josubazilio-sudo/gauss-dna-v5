import logging
from typing import Any, Dict, List
from datetime import datetime, timezone

log = logging.getLogger(__name__)


class MetricsStorage:
    def __init__(self):
        self._history: Dict[str, List[Dict[str, Any]]] = {}

    def save(self, name: str, value: Any) -> None:
        if name not in self._history:
            self._history[name] = []
        self._history[name].append({
            "value": value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def get(self, name: str) -> List[Dict[str, Any]]:
        return self._history.get(name, [])

    def get_all(self) -> Dict[str, Any]:
        return {
            name: entries[-1]["value"] if entries else None
            for name, entries in self._history.items()
        }
