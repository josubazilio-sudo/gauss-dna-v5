import logging
from typing import Dict, List

log = logging.getLogger(__name__)


class MetricDefinition:
    def __init__(self, name: str, unit: str, source: str, period: str):
        self.name = name
        self.unit = unit
        self.source = source
        self.period = period


class MetricsRegistry:
    def __init__(self):
        self._metrics: Dict[str, MetricDefinition] = {}

    def register(self, metric: MetricDefinition) -> None:
        self._metrics[metric.name] = metric

    def get(self, name: str) -> MetricDefinition:
        return self._metrics[name]

    def list_all(self) -> List[str]:
        return list(self._metrics.keys())
