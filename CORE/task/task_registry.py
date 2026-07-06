"""Registro central de tarefas."""

import logging
from typing import Dict, Any, Optional

log = logging.getLogger(__name__)


class TaskDefinition:
    def __init__(self, task_id: str, name: str, category: str):
        self.task_id = task_id
        self.name = name
        self.category = category
        self.status = "pending"
        self.payload: Optional[dict] = None
        self.result: Any = None
        self.error: Optional[str] = None
        self.executed_at: Optional[str] = None

    def __repr__(self) -> str:
        return f"TaskDefinition(id={self.task_id!r}, name={self.name!r}, status={self.status!r})"


class TaskRegistry:
    def __init__(self):
        self._tasks: Dict[str, TaskDefinition] = {}
        log.info("TaskRegistry initialized")

    def register(self, task_id: str, name: str, category: str) -> None:
        self._tasks[task_id] = TaskDefinition(task_id, name, category)
        log.debug("Task registered: %s (%s)", task_id, name)

    def get(self, task_id: str) -> Optional[TaskDefinition]:
        return self._tasks.get(task_id)

    def update_status(self, task_id: str, status: str) -> None:
        task = self._tasks.get(task_id)
        if task:
            task.status = status
            log.debug("Task %s status updated to: %s", task_id, status)
        else:
            log.warning("Cannot update status: task %s not found", task_id)

    def list_all(self) -> Dict[str, TaskDefinition]:
        return dict(self._tasks)
