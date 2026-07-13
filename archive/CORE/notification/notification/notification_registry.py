"""Registro de notificações."""

import logging
from datetime import datetime, timezone
from typing import List, Dict, Any

log = logging.getLogger(__name__)


class NotificationRegistry:
    def __init__(self):
        self._notifications: List[Dict[str, Any]] = []

    def register(self, channel: str, title: str) -> None:
        entry = {
            "channel": channel,
            "title": title,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._notifications.append(entry)
        log.debug("Notification registered: %s via %s", title, channel)

    def list_all(self) -> List[Dict[str, Any]]:
        return list(self._notifications)

    def clear(self) -> None:
        count = len(self._notifications)
        self._notifications.clear()
        log.debug("Notification registry cleared (%d entries)", count)
