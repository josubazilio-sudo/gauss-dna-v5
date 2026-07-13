"""Canais de notificação."""

import logging

log = logging.getLogger(__name__)


class NotificationChannel:
    def __init__(self, name: str, enabled: bool = True):
        self.name = name
        self.enabled = enabled
        log.debug("NotificationChannel created: %s (enabled=%s)", name, enabled)

    def send(self, title: str, message: str) -> None:
        if not self.enabled:
            log.debug("Channel '%s' disabled — skipping notification", self.name)
            return
        log.info("[%s] %s: %s", self.name, title, message)

    def enable(self) -> None:
        self.enabled = True
        log.info("Channel '%s' enabled", self.name)

    def disable(self) -> None:
        self.enabled = False
        log.info("Channel '%s' disabled", self.name)
