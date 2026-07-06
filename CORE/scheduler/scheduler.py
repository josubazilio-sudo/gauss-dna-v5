"""Coordenador central de agendamento com loop opcional."""

import logging
import threading
import time
from typing import Callable, Optional

from .job_registry import JobRegistry
from .job_executor import JobExecutor
from .scheduler_report import SchedulerReport

log = logging.getLogger(__name__)


class Scheduler:
    def __init__(self):
        self._registry = JobRegistry()
        self._executor = JobExecutor()
        self._reporter = SchedulerReport()
        self._loop_thread: Optional[threading.Thread] = None
        self._running = False
        log.info("Scheduler initialized")

    def register_job(self, name: str, interval: int, fn: Callable) -> None:
        self._registry.add(name, interval, fn)
        log.info("Job registered: %s (every %ds)", name, interval)

    def run_all(self) -> None:
        for job in self._registry.list_all():
            self._executor.execute(job)

    def start_loop(self, interval_seconds: int = 60) -> None:
        if self._running:
            log.warning("Scheduler loop already running")
            return
        self._running = True
        self._loop_thread = threading.Thread(
            target=self._loop, args=(interval_seconds,), daemon=True
        )
        self._loop_thread.start()
        log.info("Scheduler loop started (interval=%ds)", interval_seconds)

    def stop_loop(self) -> None:
        self._running = False
        log.info("Scheduler loop stopping")

    def _loop(self, interval_seconds: int) -> None:
        while self._running:
            try:
                for job in self._registry.list_all():
                    if self._executor.is_due(job):
                        self._executor.execute(job)
            except Exception as exc:
                log.error("Scheduler loop error: %s", exc)
            time.sleep(interval_seconds)

    def get_report(self) -> str:
        return self._reporter.generate(self._registry.list_all())
