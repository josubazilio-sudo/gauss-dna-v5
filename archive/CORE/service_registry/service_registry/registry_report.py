import logging
from .service_registry import ServiceRegistry

log = logging.getLogger(__name__)


class RegistryReport:
    def __init__(self, registry: ServiceRegistry):
        self._registry = registry

    def generate(self) -> str:
        lines = ["=== Service Registry Report ==="]
        for name, meta in self._registry.list_all().items():
            lines.append(f"\n{name}: {meta.get('description', '')}")
        report = "\n".join(lines)
        log.info("Registry report generated")
        return report
