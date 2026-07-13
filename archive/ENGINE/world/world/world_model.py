import logging
from typing import Any, Dict, List, Optional

from CORE.events.event_bus import EventBus
from CORE.events.events import Event

from .world_builder import build_world_model
from .world_types import WorldModel

log = logging.getLogger(__name__)


class WorldModelEngine:
    def __init__(self, event_bus: Optional[EventBus] = None):
        self._event_bus = event_bus
        self._current: Optional[WorldModel] = None

    @property
    def current(self) -> Optional[WorldModel]:
        return self._current

    def update(
        self,
        market_context: Any,
        skill_health: Optional[Dict[str, float]] = None,
        active_skills: Optional[List[str]] = None,
    ) -> WorldModel:
        self._current = build_world_model(
            market_context=market_context,
            skill_health=skill_health,
            active_skills=active_skills,
        )

        if self._event_bus:
            self._event_bus.publish(Event("world.model_updated", {
                "state": self._current.state.value,
                "quality": self._current.quality.value,
                "confidence": self._current.confidence,
                "hash": self._current.compute_hash(),
            }))

        return self._current

    def is_tradeable_environment(self) -> bool:
        if self._current is None:
            return False
        return self._current.is_tradeable()

    def get_verdict(self) -> str:
        if self._current is None:
            return "unknown"
        return f"{self._current.state.value}/{self._current.quality.value}"
