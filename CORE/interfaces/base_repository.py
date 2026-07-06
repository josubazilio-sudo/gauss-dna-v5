import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

log = logging.getLogger(__name__)


class BaseRepository(ABC):
    @abstractmethod
    def save(self, key: str, value: Any) -> None:
        pass

    @abstractmethod
    def load(self, key: str) -> Optional[Any]:
        pass

    @abstractmethod
    def delete(self, key: str) -> None:
        pass

    @abstractmethod
    def exists(self, key: str) -> bool:
        pass
