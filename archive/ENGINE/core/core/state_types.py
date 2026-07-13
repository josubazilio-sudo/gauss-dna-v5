import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


class SystemState(str, Enum):
    INITIALIZING = "INITIALIZING"
    MARKET_READY = "MARKET_READY"
    WORLD_READY = "WORLD_READY"
    SKILLS_RUNNING = "SKILLS_RUNNING"
    SKILLS_READY = "SKILLS_READY"
    GRAPH_BUILDING = "GRAPH_BUILDING"
    GRAPH_READY = "GRAPH_READY"
    HEALTH_READY = "HEALTH_READY"
    WEIGHTS_READY = "WEIGHTS_READY"
    CONSENSUS_READY = "CONSENSUS_READY"
    META_READY = "META_READY"
    POLICY_READY = "POLICY_READY"
    WORKING_MEMORY_READY = "WORKING_MEMORY_READY"
    DECISION_CONTEXT_READY = "DECISION_CONTEXT_READY"
    DECISION_READY = "DECISION_READY"
    RISK_READY = "RISK_READY"
    EXECUTION_READY = "EXECUTION_READY"
    LEARNING_READY = "LEARNING_READY"
    FINISHED = "FINISHED"
    ERROR = "ERROR"
    RECOVERY = "RECOVERY"
    RETRY = "RETRY"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class StateContext:
    cycle_id: str
    state: str
    previous_state: Optional[str] = None
    next_state: Optional[str] = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    execution_time_ms: float = 0.0
    retry_count: int = 0
    timeout_ms: float = 30000.0
    module_name: str = ""
    error_message: str = ""
    state_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "state": self.state,
            "previous_state": self.previous_state,
            "next_state": self.next_state,
            "started_at": self.started_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "execution_time_ms": self.execution_time_ms,
            "retry_count": self.retry_count,
            "timeout_ms": self.timeout_ms,
            "module_name": self.module_name,
            "error_message": self.error_message,
            "state_hash": self.state_hash,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, default=str)

    @staticmethod
    def compute_hash(ctx: "StateContext") -> str:
        raw = (
            f"{ctx.cycle_id}|{ctx.state}|{ctx.previous_state}|"
            f"{ctx.retry_count}|{ctx.module_name}|{ctx.error_message}"
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def from_dict(data: Dict) -> "StateContext":
        sa = data.get("started_at")
        if isinstance(sa, str):
            sa = datetime.fromisoformat(sa)
        ua = data.get("updated_at")
        if isinstance(ua, str):
            ua = datetime.fromisoformat(ua)
        return StateContext(
            cycle_id=data["cycle_id"],
            state=data["state"],
            previous_state=data.get("previous_state"),
            next_state=data.get("next_state"),
            started_at=sa,
            updated_at=ua,
            execution_time_ms=data.get("execution_time_ms", 0.0),
            retry_count=data.get("retry_count", 0),
            timeout_ms=data.get("timeout_ms", 30000.0),
            module_name=data.get("module_name", ""),
            error_message=data.get("error_message", ""),
            state_hash=data.get("state_hash", ""),
        )

    @staticmethod
    def from_json(json_str: str) -> "StateContext":
        return StateContext.from_dict(json.loads(json_str))


# DecisionStatus/DecisionResult nao sao redefinidos aqui — a versao real,
# usada por ENGINE.decision.decision_engine_v10, vive em
# ENGINE.decision.decision_types. Duas classes com o mesmo nome e campos
# incompativeis neste pacote geravam risco de AttributeError silencioso.
