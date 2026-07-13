import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict

log = logging.getLogger(__name__)


class BaseModule(ABC):
    def __init__(self, name: str = None, version: str = None):
        self._name = name or self.__class__.__name__
        self._version = version or "0.1.0"
        self._status = "created"
        self._started_at: datetime = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def version(self) -> str:
        return self._version

    @property
    def status(self) -> str:
        return self._status

    def get_status(self) -> Dict[str, Any]:
        return {
            "name": self._name,
            "version": self._version,
            "status": self._status,
            "started_at": self._started_at.isoformat() if self._started_at else None,
        }

    @abstractmethod
    def initialize(self) -> None:
        pass

    def start(self) -> None:
        self._status = "running"
        self._started_at = datetime.now(timezone.utc)
        log.info("Module %s started", self._name)

    def stop(self) -> None:
        self._status = "stopped"
        log.info("Module %s stopped", self._name)
