import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from .base import BaseSkill

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SkillRegistration:
    name: str
    category: str
    version: str
    author: str = "system"
    dependencies: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)
    priority: int = 0
    computational_cost: float = 1.0
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class SkillRegistry:
    def __init__(self):
        self._skills: Dict[str, BaseSkill] = {}
        self._registrations: Dict[str, SkillRegistration] = {}

    def register(self, skill: BaseSkill, registration: Optional[SkillRegistration] = None) -> None:
        if registration is None:
            registration = SkillRegistration(
                name=skill.name,
                category=skill.category,
                version=skill.version,
            )
        self._skills[skill.name] = skill
        self._registrations[skill.name] = registration
        log.info("Skill registered: %s v%s (%s)", skill.name, skill.version, skill.category)

    def unregister(self, name: str) -> None:
        self._skills.pop(name, None)
        self._registrations.pop(name, None)
        log.info("Skill unregistered: %s", name)

    def get_skill(self, name: str) -> Optional[BaseSkill]:
        return self._skills.get(name)

    def get_all_skills(self) -> List[BaseSkill]:
        return list(self._skills.values())

    def get_registration(self, name: str) -> Optional[SkillRegistration]:
        return self._registrations.get(name)

    def get_all_registrations(self) -> List[SkillRegistration]:
        return list(self._registrations.values())

    def get_skills_by_category(self, category: str) -> List[BaseSkill]:
        return [s for s in self._skills.values() if s.category == category]

    @property
    def count(self) -> int:
        return len(self._skills)

    @property
    def names(self) -> List[str]:
        return list(self._skills.keys())
