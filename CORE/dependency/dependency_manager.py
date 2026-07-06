import logging
from typing import List
from .dependency_registry import DependencyRegistry
from .dependency_validator import DependencyValidator
from .dependency_graph import DependencyGraph

log = logging.getLogger(__name__)


class DependencyManager:
    def __init__(self, registry=None, validator=None, graph=None):
        self._registry = registry or DependencyRegistry()
        self._validator = validator or DependencyValidator()
        self._graph = graph or DependencyGraph()

    def register_module(self, name: str, dependencies: List[str]) -> None:
        self._registry.register(name, dependencies)
        self._graph.add_module(name, dependencies)
        log.info(f"Module registered: {name}")

    def validate_all(self) -> bool:
        return self._validator.validate(self._registry, self._graph)

    def can_initialize(self, module: str) -> bool:
        return self._validator.can_initialize(module, self._registry)
