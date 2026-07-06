"""Fila de notificações."""

import logging
from typing import List, Dict, Any
from collections import deque

log = logging.getLogger(__name__)


class NotificationQueue:
    def __init__(self):
        self._queue = deque()

    def enqueue(self, channel: str, title: str, message: str) -> None:
        self._queue.append({
            "channel": channel,
            "title": title,
            "message": message,
        })
        log.debug("Notification queued: %s (%s)", title, channel)

    def dequeue_all(self) -> List[Dict[str, Any]]:
        items = list(self._queue)
        self._queue.clear()
        log.debug("Dequeued %d notifications", len(items))
        return items

    def size(self) -> int:
        return len(self._queue)
