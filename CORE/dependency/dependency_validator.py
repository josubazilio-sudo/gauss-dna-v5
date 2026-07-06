import logging
from typing import List
from .dependency_registry import DependencyRegistry
from .dependency_graph import DependencyGraph

log = logging.getLogger(__name__)


class DependencyValidator:
    def __init__(self):
        self._errors: List[str] = []

    def validate(self, registry: DependencyRegistry, graph: DependencyGraph) -> bool:
        self._errors.clear()
        for module in registry.list_modules():
            for dep in registry.get_dependencies(module):
                if not registry.module_exists(dep):
                    self._errors.append(f"Missing dependency: {dep} for {module}")
        if graph.has_cycle():
            self._errors.append("Circular dependency detected")
        result = len(self._errors) == 0
        log.info(f"Validation {'passed' if result else 'failed'} ({len(self._errors)} errors)")
        return result

    def can_initialize(self, module: str, registry: DependencyRegistry) -> bool:
        for dep in registry.get_dependencies(module):
            if not registry.module_exists(dep):
                log.warning(f"Cannot initialize {module}: missing dependency {dep}")
                return False
        return True

    def get_errors(self) -> List[str]:
        return self._errors
