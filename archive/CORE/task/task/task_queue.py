"""Fila de tarefas FIFO."""

import logging
from typing import Optional
from collections import deque

log = logging.getLogger(__name__)


class TaskQueue:
    def __init__(self):
        self._queue = deque()

    def enqueue(self, task_id: str) -> None:
        self._queue.append(task_id)
        log.debug("Task enqueued: %s (queue size: %d)", task_id, len(self._queue))

    def dequeue(self) -> Optional[str]:
        task_id = self._queue.popleft() if self._queue else None
        if task_id:
            log.debug("Task dequeued: %s (queue size: %d)", task_id, len(self._queue))
        return task_id

    def size(self) -> int:
        return len(self._queue)

    def clear(self) -> None:
        count = len(self._queue)
        self._queue.clear()
        log.debug("Queue cleared (%d tasks)", count)
