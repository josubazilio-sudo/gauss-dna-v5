import hashlib
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from CORE.events.event_bus import EventBus
from CORE.events.events import Event, EventTypes
from ENGINE.memory.working_memory_types import WorkingMemory

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorkingMemoryContext:
    cycle_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    context_hash: str = ""
    memory: Optional[WorkingMemory] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        if self.memory is not None:
            d["memory"] = self.memory.to_dict()
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, default=str)

    @staticmethod
    def from_memory(memory: WorkingMemory) -> "WorkingMemoryContext":
        ctx = WorkingMemoryContext(
            cycle_id=memory.cycle_id,
            timestamp=datetime.now(timezone.utc),
            memory=memory,
            context_hash="",
        )
        return WorkingMemoryContext(
            cycle_id=ctx.cycle_id,
            timestamp=ctx.timestamp,
            memory=ctx.memory,
            context_hash=WorkingMemoryContext.compute_hash(ctx),
        )

    @staticmethod
    def compute_hash(ctx: "WorkingMemoryContext") -> str:
        wm_hash = WorkingMemory.compute_hash(ctx.memory) if ctx.memory else "none"
        return hashlib.sha256(
            f"{ctx.cycle_id}|{wm_hash}".encode("utf-8"),
        ).hexdigest()

    @staticmethod
    def from_dict(data: Dict) -> "WorkingMemoryContext":
        from ENGINE.memory.working_memory import WorkingMemoryManager
        ts = data.get("timestamp")
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        mem = data.get("memory")
        if isinstance(mem, dict):
            mem = WorkingMemoryManager.from_dict(mem)
        return WorkingMemoryContext(
            cycle_id=data["cycle_id"],
            timestamp=ts,
            memory=mem,
            context_hash=data.get("context_hash", ""),
        )

    @staticmethod
    def from_json(json_str: str) -> "WorkingMemoryContext":
        return WorkingMemoryContext.from_dict(json.loads(json_str))


class DecisionContextBuilder:

    def __init__(self, event_bus: Optional[EventBus] = None):
        self._event_bus = event_bus

    def build(self, memory: WorkingMemory) -> WorkingMemoryContext:
        ctx = WorkingMemoryContext.from_memory(memory)
        self._publish(ctx)
        return ctx

    def _publish(self, ctx: WorkingMemoryContext) -> None:
        if self._event_bus is None:
            return
        try:
            self._event_bus.publish(Event(
                EventTypes.DECISION_CONTEXT_CREATED,
                {"cycle_id": ctx.cycle_id, "context_hash": ctx.context_hash},
            ))
        except Exception as e:
            log.error("Failed to publish decision.context.created: %s", e)
