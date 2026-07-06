import logging
from abc import ABC, abstractmethod

log = logging.getLogger(__name__)


class BaseService(ABC):
    @abstractmethod
    def initialize(self) -> None:
        pass

    @abstractmethod
    def shutdown(self) -> None:
        pass

    @abstractmethod
    def status(self) -> dict:
        pass
