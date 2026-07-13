import logging
from typing import Any, Dict

log = logging.getLogger(__name__)


class MetricsReport:
    def generate(self, data: Dict[str, Any], indicators: Dict[str, Any]) -> str:
        lines = ["=== Relatorio de Metricas ==="]
        for name, value in data.items():
            lines.append(f"  {name}: {value}")
        if indicators:
            lines.append("\nIndicadores:")
            for name, value in indicators.items():
                lines.append(f"  {name}: {value}")
        return "\n".join(lines)
