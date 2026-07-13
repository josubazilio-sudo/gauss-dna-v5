"""Execução de tarefas com suporte a callable."""

import logging
from datetime import datetime, timezone
from typing import Any

from .task_registry import TaskDefinition

log = logging.getLogger(__name__)


class TaskExecutor:
    def execute(self, task: TaskDefinition) -> None:
        log.info("Executing task: %s (%s)", task.task_id, task.name)
        try:
            payload = getattr(task, "payload", None)
            fn = getattr(task, "_callable", None)
            if fn is not None:
                result = fn(payload)
                task.result = result
                task.executed_at = datetime.now(timezone.utc).isoformat()
                task.status = "completed"
                log.info("Task %s completed successfully", task.task_id)
            elif payload and "action" in payload:
                action = payload["action"]
                log.info("Task %s running action: %s", task.task_id, action)
                task.status = "completed"
                task.executed_at = datetime.now(timezone.utc).isoformat()
            else:
                log.warning("Task %s has no callable or action — marking as done", task.task_id)
                task.status = "completed"
                task.executed_at = datetime.now(timezone.utc).isoformat()
        except Exception as exc:
            task.status = "failed"
            task.error = str(exc)
            log.error("Task %s failed: %s", task.task_id, exc)

    def execute_callable(self, task: TaskDefinition, fn: Any, payload: Any = None) -> None:
        task._callable = fn
        task.payload = payload
        self.execute(task)
