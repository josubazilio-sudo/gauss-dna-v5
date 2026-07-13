"""Relatórios do scheduler."""

import logging

from .job_registry import Job

log = logging.getLogger(__name__)


class SchedulerReport:
    def generate(self, jobs: list) -> str:
        lines = ["=== Scheduler Report ==="]
        if not jobs:
            lines.append("  (no jobs registered)")
        else:
            for job in jobs:
                lines.append(f"  {job.name}: interval={job.interval}s")
        log.debug("Generated scheduler report with %d jobs", len(jobs))
        return "\n".join(lines)
