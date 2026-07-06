import logging
from typing import Dict, List, Set

log = logging.getLogger(__name__)


class DependencyGraph:
    def __init__(self):
        self._graph: Dict[str, List[str]] = {}

    def add_module(self, name: str, dependencies: List[str]) -> None:
        self._graph[name] = dependencies
        log.debug(f"Added to graph: {name}")

    def has_cycle(self) -> bool:
        visited: Set[str] = set()
        stack: Set[str] = set()

        def dfs(node: str) -> bool:
            visited.add(node)
            stack.add(node)
            for dep in self._graph.get(node, []):
                if dep not in visited:
                    if dfs(dep):
                        return True
                elif dep in stack:
                    log.warning(f"Cycle detected involving {node} -> {dep}")
                    return True
            stack.remove(node)
            return False

        for module in self._graph:
            if module not in visited:
                if dfs(module):
                    return True
        return False

    def get_dependents(self, module: str) -> List[str]:
        return [
            m for m, deps in self._graph.items()
            if module in deps
        ]
