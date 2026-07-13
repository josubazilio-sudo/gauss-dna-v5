"""Registro de eventos de permissão."""

import logging
from datetime import datetime, timezone
from typing import List, Dict, Any

log = logging.getLogger(__name__)


class PermissionAudit:
    def __init__(self):
        self._events: List[Dict[str, Any]] = []

    def log(self, result: str, detail: str) -> None:
        event = {
            "result": result,
            "detail": detail,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._events.append(event)
        log.debug("Permission audit: %s — %s", result, detail)

    def get_events(self) -> List[Dict[str, Any]]:
        return list(self._events)
