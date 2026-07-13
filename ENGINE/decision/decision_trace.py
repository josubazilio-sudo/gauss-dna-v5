import hashlib
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from CORE.events.event_bus import EventBus
from CORE.events.events import Event, EventTypes

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class StepRecord:
    step_name: str
    timestamp: datetime
    duration_ms: float
    result: str
    step_hash: str
    module_version: str
    observations: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_name": self.step_name,
            "timestamp": self.timestamp.isoformat(),
            "duration_ms": self.duration_ms,
            "result": self.result,
            "step_hash": self.step_hash,
            "module_version": self.module_version,
            "observations": self.observations,
        }


@dataclass(frozen=True)
class DecisionTrace:
    cycle_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    steps: List[StepRecord] = field(default_factory=list)
    trace_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "timestamp": self.timestamp.isoformat(),
            "steps": [s.to_dict() for s in self.steps],
            "trace_hash": self.trace_hash,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, default=str)

    @staticmethod
    def compute_hash(trace: "DecisionTrace") -> str:
        parts = [f"{trace.cycle_id}|{len(trace.steps)}"]
        for s in trace.steps:
            parts.append(f"{s.step_name}|{s.step_hash}|{s.duration_ms}")
        return hashlib.sha256("||".join(parts).encode("utf-8")).hexdigest()

    @staticmethod
    def from_dict(data: Dict) -> "DecisionTrace":
        ts = data.get("timestamp")
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        steps = []
        for s in data.get("steps", []):
            st = s.get("timestamp")
            if isinstance(st, str):
                st = datetime.fromisoformat(st)
            steps.append(StepRecord(
                step_name=s["step_name"],
                timestamp=st,
                duration_ms=s["duration_ms"],
                result=s["result"],
                step_hash=s["step_hash"],
                module_version=s.get("module_version", ""),
                observations=s.get("observations", ""),
            ))
        return DecisionTrace(
            cycle_id=data["cycle_id"],
            timestamp=ts,
            steps=steps,
            trace_hash=data.get("trace_hash", ""),
        )

    @staticmethod
    def from_json(json_str: str) -> "DecisionTrace":
        return DecisionTrace.from_dict(json.loads(json_str))


class DecisionTraceRecorder:

    PIPELINE_ORDER = [
        "cycle", "world_model", "skills", "evidence_graph",
        "health_score", "dynamic_weights", "consensus", "meta",
        "policy", "decision", "risk", "execution", "outcome",
    ]

    def __init__(self, event_bus: Optional[EventBus] = None):
        self._event_bus = event_bus
        self._current: Optional[DecisionTrace] = None
        self._cycle_start: Optional[datetime] = None

    @property
    def current(self) -> Optional[DecisionTrace]:
        return self._current

    def start_cycle(self, cycle_id: str) -> DecisionTrace:
        self._cycle_start = datetime.now(timezone.utc)
        trace = DecisionTrace(
            cycle_id=cycle_id,
            timestamp=self._cycle_start,
            steps=[],
            trace_hash="",
        )
        final = DecisionTrace(
            cycle_id=trace.cycle_id,
            timestamp=trace.timestamp,
            steps=[],
            trace_hash=DecisionTrace.compute_hash(trace),
        )
        self._current = final
        self._publish(final)
        return final

    def record_step(
        self,
        step_name: str,
        result: str,
        step_hash: str = "",
        module_version: str = "10.0.0",
        observations: str = "",
    ) -> DecisionTrace:
        if self._current is None:
            raise RuntimeError("No active cycle. Call start_cycle first.")

        now = datetime.now(timezone.utc)
        duration = 0.0
        if self._cycle_start is not None:
            duration = (now - self._cycle_start).total_seconds() * 1000

        step = StepRecord(
            step_name=step_name,
            timestamp=now,
            duration_ms=round(duration, 2),
            result=result,
            step_hash=step_hash or hashlib.sha256(
                f"{step_name}|{now.isoformat()}|{result}".encode("utf-8"),
            ).hexdigest()[:16],
            module_version=module_version,
            observations=observations,
        )

        new_steps = list(self._current.steps) + [step]
        new_trace = DecisionTrace(
            cycle_id=self._current.cycle_id,
            timestamp=self._current.timestamp,
            steps=new_steps,
            trace_hash="",
        )
        final = DecisionTrace(
            cycle_id=new_trace.cycle_id,
            timestamp=new_trace.timestamp,
            steps=new_trace.steps,
            trace_hash=DecisionTrace.compute_hash(new_trace),
        )
        self._current = final
        self._publish(final)
        return final

    def get_pipeline_status(self) -> List[str]:
        if self._current is None:
            return []
        return [s.step_name for s in self._current.steps]

    def _publish(self, trace: DecisionTrace) -> None:
        if self._event_bus is None:
            return
        try:
            self._event_bus.publish(Event(
                EventTypes.DECISION_TRACE_CREATED,
                {"cycle_id": trace.cycle_id, "trace_hash": trace.trace_hash},
            ))
        except Exception as e:
            log.error("Failed to publish decision.trace.created: %s", e)

    def clear(self) -> None:
        self._current = None
        self._cycle_start = None
