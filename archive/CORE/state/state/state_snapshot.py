"""Snapshots de estado."""

import logging
from datetime import datetime, timezone
from typing import List, Dict, Any

log = logging.getLogger(__name__)


class StateSnapshot:
    def __init__(self):
        self._history: List[Dict[str, Any]] = []

    def record(self, state: str) -> None:
        entry = {
            "state": state,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._history.append(entry)
        log.debug("Snapshot recorded: %s", state)

    def get_history(self) -> List[Dict[str, Any]]:
        return list(self._history)

    def clear(self) -> None:
        count = len(self._history)
        self._history.clear()
        log.debug("Snapshot history cleared (%d entries)", count)
