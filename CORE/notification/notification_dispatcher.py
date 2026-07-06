"""Despacho de notificações via registro de canais."""

import logging
from typing import Callable, Dict

log = logging.getLogger(__name__)


class NotificationDispatcher:
    def __init__(self):
        self._channels: Dict[str, Callable[[str, str], None]] = {}
        log.info("NotificationDispatcher initialized")

    def register_channel(self, name: str, handler: Callable[[str, str], None]) -> None:
        self._channels[name] = handler
        log.info("Notification channel registered: %s", name)

    def unregister_channel(self, name: str) -> None:
        self._channels.pop(name, None)
        log.info("Notification channel unregistered: %s", name)

    def dispatch(self, channel: str, title: str, message: str) -> None:
        handler = self._channels.get(channel)
        if handler:
            try:
                handler(title, message)
                log.info("Notification dispatched via '%s': %s", channel, title)
            except Exception as exc:
                log.error("Notification channel '%s' failed: %s", channel, exc)
        else:
            log.info("Notification logged (no handler for '%s'): %s", channel, title)
