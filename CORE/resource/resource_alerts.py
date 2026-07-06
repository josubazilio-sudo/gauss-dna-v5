"""Alertas de recursos."""

import logging

log = logging.getLogger(__name__)


class ResourceAlerts:
    def trigger(self, message: str) -> None:
        log.warning("Resource alert triggered: %s", message)
