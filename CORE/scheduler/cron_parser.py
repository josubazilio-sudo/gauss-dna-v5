"""Parser de expressões cron."""

import logging

log = logging.getLogger(__name__)


class CronParser:
    @staticmethod
    def parse(expression: str) -> dict:
        parts = expression.split()
        if len(parts) != 5:
            log.error("Invalid cron expression: %s", expression)
            raise ValueError(f"Invalid cron expression: {expression}")
        result = {
            "minute": parts[0],
            "hour": parts[1],
            "day": parts[2],
            "month": parts[3],
            "weekday": parts[4],
        }
        log.debug("Parsed cron '%s' -> %s", expression, result)
        return result
