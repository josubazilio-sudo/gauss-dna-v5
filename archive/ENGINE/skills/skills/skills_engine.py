import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, List, Optional

from CORE.events.event_bus import EventBus
from CORE.events.events import Event

from .base import BaseSkill
from .skill_opinion import SkillOpinion
from .skill_registry import SkillRegistry

log = logging.getLogger(__name__)


class SkillsEngine:
    def __init__(self, event_bus: EventBus, registry: Optional[SkillRegistry] = None):
        self._registry = registry or SkillRegistry()
        self._event_bus = event_bus
        self._executor = ThreadPoolExecutor(max_workers=10)

    @property
    def registry(self) -> SkillRegistry:
        return self._registry

    def register_skill(self, skill: BaseSkill) -> None:
        self._registry.register(skill)

    def execute_all(self, market_context: Any, world_model: Any = None, timeout: int = 30) -> List[SkillOpinion]:
        opinions: List[SkillOpinion] = []
        skills = self._registry.get_all_skills()

        if not skills:
            log.warning("No skills registered — nothing to execute")
            return opinions

        futures = {}
        for skill in skills:
            future = self._executor.submit(self._run_skill, skill, market_context, world_model)
            futures[future] = skill.name

        for future in as_completed(futures, timeout=timeout):
            skill_name = futures[future]
            try:
                opinion = future.result(timeout=5)
                opinions.append(opinion)
            except Exception as e:
                log.error("Skill %s failed: %s", skill_name, e)
                opinions.append(SkillOpinion(
                    skill_name=skill_name,
                    confidence=0.0,
                    risk=1.0,
                    probability=0.0,
                    evidence=["Skill execution failed"],
                    observations=f"Error: {e}",
                    success=False,
                ))

        self._event_bus.publish(Event("skills.opinions_ready", {
            "opinions": opinions,
            "count": len(opinions),
            "skill_names": [o.skill_name for o in opinions],
        }))

        return opinions

    def _run_skill(self, skill: BaseSkill, market_context: Any, world_model: Any) -> SkillOpinion:
        return skill.analyze(market_context, world_model)
