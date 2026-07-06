"""Coordenador central de tarefas."""

import logging

from .task_registry import TaskRegistry
from .task_executor import TaskExecutor
from .task_queue import TaskQueue
from .task_validator import TaskValidator
from .task_report import TaskReport

log = logging.getLogger(__name__)


class TaskManager:
    def __init__(self):
        self._registry = TaskRegistry()
        self._executor = TaskExecutor()
        self._queue = TaskQueue()
        self._validator = TaskValidator()
        self._reporter = TaskReport()
        log.info("TaskManager initialized")

    def submit(self, task_id: str, name: str, category: str, payload: dict) -> None:
        errors = self._validator.validate(payload)
        if errors:
            for e in errors:
                log.error("Task rejected: %s", e)
            return
        self._registry.register(task_id, name, category)
        task = self._registry.get(task_id)
        if task:
            task.payload = payload
        self._queue.enqueue(task_id)
        log.info("Task submitted: %s (%s)", task_id, name)

    def process_next(self) -> None:
        task_id = self._queue.dequeue()
        if task_id:
            task = self._registry.get(task_id)
            if task:
                log.info("Processing task: %s", task_id)
                self._executor.execute(task)
                self._registry.update_status(task_id, task.status)
            else:
                log.warning("Task %s not found in registry", task_id)
        else:
            log.debug("No tasks in queue to process")

    def get_report(self) -> str:
        return self._reporter.generate(self._registry.list_all())
