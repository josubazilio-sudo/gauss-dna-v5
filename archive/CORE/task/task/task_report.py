"""Relatórios de tarefas."""

import logging
from typing import Dict

from .task_registry import TaskDefinition

log = logging.getLogger(__name__)


class TaskReport:
    def generate(self, tasks: Dict[str, TaskDefinition]) -> str:
        lines = ["=== Task Report ==="]
        if not tasks:
            lines.append("  (no tasks)")
        else:
            for task_id, task in tasks.items():
                status_info = task.status
                if task.error:
                    status_info += f" [error: {task.error}]"
                lines.append(f"  {task_id}: {task.name} [{status_info}]")
        log.debug("Generated task report with %d tasks", len(tasks))
        return "\n".join(lines)
