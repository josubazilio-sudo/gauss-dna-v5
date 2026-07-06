"""Coordenador central de notificações."""

import logging

from .notification_registry import NotificationRegistry
from .notification_dispatcher import NotificationDispatcher
from .notification_channel import NotificationChannel
from .notification_queue import NotificationQueue
from .notification_report import NotificationReport

log = logging.getLogger(__name__)


class NotificationManager:
    def __init__(self):
        self._registry = NotificationRegistry()
        self._dispatcher = NotificationDispatcher()
        self._queue = NotificationQueue()
        self._reporter = NotificationReport()
        log.info("NotificationManager initialized")

    def register_channel(self, name: str, handler) -> None:
        self._dispatcher.register_channel(name, handler)

    def send(self, channel: str, title: str, message: str) -> None:
        self._queue.enqueue(channel, title, message)
        self._dispatcher.dispatch(channel, title, message)
        self._registry.register(channel, title)
        log.info("Notification sent: %s via %s", title, channel)

    def get_report(self) -> str:
        return self._reporter.generate(self._registry.list_all())

    def flush_queue(self) -> None:
        items = self._queue.dequeue_all()
        for item in items:
            self._dispatcher.dispatch(item["channel"], item["title"], item["message"])
            self._registry.register(item["channel"], item["title"])
        log.info("Flushed %d queued notifications", len(items))
