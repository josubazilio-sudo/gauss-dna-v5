"""Registro de jobs agendados."""

import logging
from typing import List, Dict, Callable, Optional

log = logging.getLogger(__name__)


class Job:
    def __init__(self, name: str, interval: int, fn: Callable):
        self.name = name
        self.interval = interval
        self.fn = fn

    def __repr__(self) -> str:
        return f"Job(name={self.name!r}, interval={self.interval})"


class JobRegistry:
    def __init__(self):
        self._jobs: Dict[str, Job] = {}
        log.info("JobRegistry initialized")

    def add(self, name: str, interval: int, fn: Callable) -> None:
        if not name:
            raise ValueError("Job name cannot be empty")
        self._jobs[name] = Job(name, interval, fn)
        log.debug("Job added: %s", name)

    def get(self, name: str) -> Optional[Job]:
        return self._jobs.get(name)

    def list_all(self) -> List[Job]:
        return list(self._jobs.values())

    def remove(self, name: str) -> None:
        self._jobs.pop(name, None)
        log.debug("Job removed: %s", name)
