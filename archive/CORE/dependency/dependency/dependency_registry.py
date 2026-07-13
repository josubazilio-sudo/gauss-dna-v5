import logging
from typing import Dict, List

log = logging.getLogger(__name__)


class DependencyRegistry:
    def __init__(self):
        self._modules: Dict[str, List[str]] = {}

    def register(self, name: str, dependencies: List[str]) -> None:
        self._modules[name] = dependencies
        log.debug(f"Registered module: {name}")

    def get_dependencies(self, name: str) -> List[str]:
        return self._modules.get(name, [])

    def module_exists(self, name: str) -> bool:
        return name in self._modules

    def list_modules(self) -> Dict[str, List[str]]:
        return dict(self._modules)
