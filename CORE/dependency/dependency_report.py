import logging
from typing import Dict, List
from .dependency_registry import DependencyRegistry

log = logging.getLogger(__name__)


class DependencyReport:
    def __init__(self, registry: DependencyRegistry):
        self._registry = registry

    def generate(self) -> str:
        lines = ["=== Dependency Report ==="]
        for module, deps in self._registry.list_modules().items():
            lines.append(f"\n{module}:")
            for dep in deps:
                lines.append(f"  <- {dep}")
        report = "\n".join(lines)
        log.info("Dependency report generated")
        return report
