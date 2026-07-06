import logging
from abc import abstractmethod
from typing import Any, Dict

from .base_module import BaseModule

log = logging.getLogger(__name__)


class BaseProvider(BaseModule):
    @abstractmethod
    def connect(self) -> bool:
        pass

    @abstractmethod
    def disconnect(self) -> None:
        pass

    @abstractmethod
    def fetch(self, resource: str, **kwargs) -> Dict[str, Any]:
        pass
