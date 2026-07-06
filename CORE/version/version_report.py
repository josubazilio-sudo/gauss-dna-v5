"""
Relatórios de versionamento.
"""

from .version_registry import VersionRegistry
from .baseline_manager import BaselineManager


class VersionReport:
    def __init__(self, registry: VersionRegistry, baselines: BaselineManager):
        self._registry = registry
        self._baselines = baselines

    def generate(self) -> str:
        lines = ["=== Relatorio de Versoes ==="]
        for module, version in self._registry.all_versions().items():
            lines.append(f"{module}: {version}")
        lines.append(f"\nBaselines: {len(self._baselines.list_all())}")
        return "\n".join(lines)
