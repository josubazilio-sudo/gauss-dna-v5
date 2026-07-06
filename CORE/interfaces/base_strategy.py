import logging
from abc import abstractmethod
from typing import Any, Dict

from .base_module import BaseModule

log = logging.getLogger(__name__)


class BaseStrategy(BaseModule):
    @abstractmethod
    def analyze(self, data: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    def score(self, data: Dict[str, Any]) -> float:
        pass
