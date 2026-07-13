import logging
from abc import ABC, abstractmethod
from typing import Any

from .skill_opinion import SkillOpinion

log = logging.getLogger(__name__)


class BaseSkill(ABC):
    def __init__(self, name: str, version: str = "1.0.0", category: str = "general"):
        self._name = name
        self._version = version
        self._category = category

    @property
    def name(self) -> str:
        return self._name

    @property
    def version(self) -> str:
        return self._version

    @property
    def category(self) -> str:
        return self._category

    @abstractmethod
    def analyze(self, market_context: Any, world_model: Any = None) -> SkillOpinion:
        ...
