import logging
from typing import Any, Dict

log = logging.getLogger(__name__)


class MetricsDashboard:
    def __init__(self):
        self._panels: Dict[str, Any] = {}

    def add_panel(self, name: str, value: Any) -> None:
        self._panels[name] = value

    def render(self) -> str:
        lines = ["=== Dashboard de Metricas ==="]
        for name, value in self._panels.items():
            lines.append(f"  {name}: {value}")
        return "\n".join(lines)
