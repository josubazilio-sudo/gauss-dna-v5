import logging
from abc import abstractmethod
from typing import Any

from .base_service import BaseService

log = logging.getLogger(__name__)


class BaseEngine(BaseService):
    @abstractmethod
    def execute(self, **kwargs) -> dict:
        pass

    @abstractmethod
    def validate(self, **kwargs) -> bool:
        pass
