import logging
from abc import ABC, abstractmethod
from typing import Any, List

log = logging.getLogger(__name__)


class BaseValidator(ABC):
    @abstractmethod
    def validate(self, data: Any) -> bool:
        pass

    @abstractmethod
    def get_errors(self) -> List[str]:
        pass

    @abstractmethod
    def clear(self) -> None:
        pass
