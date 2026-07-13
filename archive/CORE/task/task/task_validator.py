"""Validador de tarefas."""

import logging
from typing import List

log = logging.getLogger(__name__)


class TaskValidator:
    REQUIRED_FIELDS = ["action"]

    def validate(self, payload: dict) -> List[str]:
        errors = []
        if not isinstance(payload, dict):
            errors.append("Payload must be a dict")
            log.error("Validation failed: payload is not a dict")
            return errors
        for field in self.REQUIRED_FIELDS:
            if field not in payload:
                errors.append(f"Required field '{field}' is missing")
        if errors:
            log.warning("Task validation errors: %s", errors)
        return errors
