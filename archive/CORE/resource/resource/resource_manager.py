"""Coordenador central de recursos."""

import logging

from .resource_monitor import ResourceMonitor
from .resource_limiter import ResourceLimiter
from .resource_tracker import ResourceTracker
from .resource_alerts import ResourceAlerts
from .resource_report import ResourceReport

log = logging.getLogger(__name__)


class ResourceManager:
    def __init__(self):
        self._monitor = ResourceMonitor()
        self._limiter = ResourceLimiter()
        self._tracker = ResourceTracker()
        self._alerts = ResourceAlerts()
        self._reporter = ResourceReport()
        log.info("ResourceManager initialized")

    def check_limits(self) -> bool:
        try:
            usage = self._monitor.get_usage()
            log.debug("Current usage: %s", usage)
            if self._limiter.exceeded(usage):
                self._alerts.trigger("Resource limit exceeded")
                log.warning("Resource usage above limits: %s", usage)
                return False
            self._tracker.record(usage)
            return True
        except Exception as exc:
            log.error("Failed to check resource limits: %s", exc)
            return False

    def get_report(self) -> str:
        return self._reporter.generate(self._tracker.get_history())
