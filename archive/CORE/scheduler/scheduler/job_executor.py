"""Execução de jobs agendados com controle de última execução."""

import logging
import time
from datetime import datetime, timezone

from .job_registry import Job

log = logging.getLogger(__name__)


class JobExecutor:
    def __init__(self):
        self._last_run: dict = {}

    def execute(self, job: Job) -> None:
        try:
            job.fn()
            self._last_run[job.name] = time.time()
            log.info("Job executed: %s", job.name)
        except Exception as exc:
            log.error("Job '%s' failed: %s", job.name, exc)

    def is_due(self, job: Job) -> bool:
        last = self._last_run.get(job.name, 0)
        return (time.time() - last) >= job.interval

    def last_run(self, job_name: str) -> str:
        ts = self._last_run.get(job_name)
        if ts is None:
            return "never"
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
