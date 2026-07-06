"""Registro de eventos de segurança."""

import logging
from datetime import datetime, timezone
from typing import List, Dict, Any

log = logging.getLogger(__name__)


class SecurityAudit:
    def __init__(self):
        self._events: List[Dict[str, Any]] = []

    def log(self, action: str, detail: str) -> None:
        event = {
            "action": action,
            "detail": detail,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._events.append(event)
        log.debug("Audit event: %s — %s", action, detail)

    def get_events(self) -> List[Dict[str, Any]]:
        return list(self._events)

    def clear(self) -> None:
        count = len(self._events)
        self._events.clear()
        log.debug("Cleared %d audit events", count)
