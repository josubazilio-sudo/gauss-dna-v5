"""Rastreamento de alocação de recursos."""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Any

log = logging.getLogger(__name__)


class ResourceTracker:
    def __init__(self):
        self._history: List[Dict[str, Any]] = []

    def record(self, usage: Dict[str, float]) -> None:
        entry = {
            "usage": dict(usage),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._history.append(entry)
        log.debug("Resource usage recorded: %s", usage)

    def get_history(self) -> List[Dict[str, Any]]:
        return list(self._history)

    def clear(self) -> None:
        count = len(self._history)
        self._history.clear()
        log.debug("Cleared %d history entries", count)
