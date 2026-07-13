import logging

log = logging.getLogger(__name__)


class Migration:
    def __init__(self):
        self._log = log

    def run(self, module: str, from_version: str, to_version: str) -> bool:
        self._log.info(f"Migrando {module}: {from_version} -> {to_version}")
        return True

    def rollback(self, module: str, version: str) -> bool:
        self._log.info(f"Rollback {module} para {version}")
        return True
