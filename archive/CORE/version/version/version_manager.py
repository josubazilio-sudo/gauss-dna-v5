import logging

from .version_registry import VersionRegistry
from .baseline_manager import BaselineManager

log = logging.getLogger(__name__)


class VersionManager:
    def __init__(self):
        self._log = log
        self._registry = VersionRegistry()
        self._baselines = BaselineManager()

    def bump_major(self, module: str) -> str:
        version = self._registry.bump_major(module)
        self._log.info(f"Major bump: {module} -> {version}")
        return version

    def bump_minor(self, module: str) -> str:
        version = self._registry.bump_minor(module)
        self._log.info(f"Minor bump: {module} -> {version}")
        return version

    def bump_patch(self, module: str) -> str:
        version = self._registry.bump_patch(module)
        self._log.info(f"Patch bump: {module} -> {version}")
        return version

    def create_baseline(self, module: str) -> None:
        version = self._registry.get_version(module)
        self._baselines.create(module, version)
        self._log.info(f"Baseline criada: {module}@{version}")
