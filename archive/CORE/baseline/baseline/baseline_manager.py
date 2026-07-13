import logging

from .baseline_registry import BaselineRegistry
from .baseline_validator import BaselineValidator
from .baseline_comparator import BaselineComparator
from .rollback_manager import RollbackManager
from .snapshot_manager import SnapshotManager

log = logging.getLogger(__name__)


class BaselineManager:
    def __init__(self):
        self._log = log
        self._registry = BaselineRegistry()
        self._validator = BaselineValidator()
        self._comparator = BaselineComparator()
        self._rollback = RollbackManager()
        self._snapshot = SnapshotManager()

    def certify(self, name: str, version: str, artifacts: list) -> bool:
        errors = self._validator.validate(artifacts)
        if errors:
            for e in errors:
                self._log.error(f"Certification failed: {e}")
            return False
        snapshot_id = self._snapshot.create(name, version)
        self._registry.register(name, version, snapshot_id)
        self._log.info(f"Baseline certificada: {name}@{version}")
        return True

    def rollback(self, name: str, version: str) -> bool:
        baseline = self._registry.get(name, version)
        if not baseline:
            self._log.error(f"Baseline nao encontrada: {name}@{version}")
            return False
        return self._rollback.execute(baseline)

    def compare(self, name: str, v1: str, v2: str) -> dict:
        b1 = self._registry.get(name, v1)
        b2 = self._registry.get(name, v2)
        return self._comparator.compare(b1, b2)
