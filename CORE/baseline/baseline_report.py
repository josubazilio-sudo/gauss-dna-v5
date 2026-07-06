"""
Relatórios de certificação de Baseline.
"""

from .baseline_registry import BaselineRegistry


class BaselineReport:
    def __init__(self, registry: BaselineRegistry):
        self._registry = registry

    def generate(self) -> str:
        lines = ["=== Relatorio de Baselines Certificadas ==="]
        for key, baseline in self._registry.all().items():
            lines.append(f"  {baseline['name']}@{baseline['version']}")
            lines.append(f"    Snapshot: {baseline['snapshot_id']}")
            lines.append(f"    Status: {baseline['status']}")
        return "\n".join(lines)
