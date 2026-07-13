import logging
from .metrics_registry import MetricsRegistry
from .metrics_collector import MetricsCollector
from .metrics_calculator import MetricsCalculator
from .metrics_storage import MetricsStorage
from .metrics_report import MetricsReport

log = logging.getLogger(__name__)


class MetricsEngine:
    def __init__(self):
        self._registry = MetricsRegistry()
        self._collector = MetricsCollector()
        self._calculator = MetricsCalculator()
        self._storage = MetricsStorage()
        self._reporter = MetricsReport()

    def collect_all(self) -> None:
        for name in self._registry.list_all():
            value = self._collector.collect(name)
            self._storage.save(name, value)
        log.info("Coleta de metricas concluida")

    def get_report(self) -> str:
        data = self._storage.get_all()
        indicators = self._calculator.calculate(data)
        return self._reporter.generate(data, indicators)
