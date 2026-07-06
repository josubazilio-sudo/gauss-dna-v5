import logging
from typing import Any, Dict

log = logging.getLogger(__name__)


class MetricsCalculator:
    def calculate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        indicators: Dict[str, Any] = {}
        if "errors" in data:
            error_count = len(data["errors"]) if isinstance(data["errors"], list) else data["errors"]
            indicators["reliability"] = round(max(0, 100 - error_count), 2)
        if "startup_time" in data:
            indicators["performance"] = data["startup_time"]
        if "response_times" in data:
            times = data["response_times"]
            if isinstance(times, list) and times:
                indicators["avg_response_time"] = round(sum(times) / len(times), 3)
        if "memory_usage" in data:
            indicators["memory_mb"] = data["memory_usage"]
        return indicators
