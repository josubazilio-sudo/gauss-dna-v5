
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import hashlib
import json

class DecisionStatus(Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    HOLD = "HOLD"

@dataclass(frozen=True)
class DecisionContext:
    cycle_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    context_hash: str = ""
    
    # Sources of Decision
    world_model: Optional[Any] = None
    skill_opinions: Optional[Dict[str, Any]] = None
    evidence_graph: Optional[Any] = None
    health_scores: Optional[Dict[str, float]] = None
    weight_distribution: Optional[Dict[str, float]] = None
    council_verdict: Optional[str] = None
    meta_verdict: Optional[str] = None
    policy_verdict: Optional[str] = None
    working_memory: Optional[Any] = None # Assuming WorkingMemory has to_dict/to_json
    decision_trace: Optional[Any] = None # Assuming DecisionTrace has to_dict/to_json

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        
        # Serialization for complex types
        for field in ["world_model", "skill_opinions", "evidence_graph", "working_memory", "decision_trace"]:
            obj = getattr(self, field)
            if obj is not None and hasattr(obj, "to_dict"):
                d[field] = obj.to_dict()
        
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, default=str)

    @staticmethod
    def compute_hash(ctx: "DecisionContext") -> str:
        wm_hash = hashlib.sha256(str(ctx.working_memory).encode()).hexdigest() if ctx.working_memory else "none"
        skill_hash = hashlib.sha256(str(ctx.skill_opinions).encode()).hexdigest() if ctx.skill_opinions else "none"
        meta_hash = str(ctx.meta_verdict) if ctx.meta_verdict else "none"
        policy_hash = str(ctx.policy_verdict) if ctx.policy_verdict else "none"

        raw_string = f"{ctx.cycle_id}|{wm_hash}|{skill_hash}|{meta_hash}|{policy_hash}"
        return hashlib.sha256(raw_string.encode()).hexdigest()

    @staticmethod
    def from_dict(data: Dict) -> "DecisionContext":
        # This method will need to correctly deserialize all nested structures
        # For now, we'll assume simple types or that nested structures have their own from_dict/from_json
        ts = data.get("timestamp")
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        
        # Placeholder deserialization - actual implementation depends on nested types
        working_memory = data.get("working_memory")
        if isinstance(working_memory, dict):
             # Assuming WorkingMemory has a from_dict method
             # from ENGINE.memory.working_memory import WorkingMemoryManager # Example import
             # memory = WorkingMemoryManager.from_dict(memory)
             pass # Placeholder

        decision_trace = data.get("decision_trace")
        if isinstance(decision_trace, dict):
            # Assuming DecisionTrace has a from_dict method
            pass # Placeholder

        return DecisionContext(
            cycle_id=data["cycle_id"],
            timestamp=ts,
            context_hash=data.get("context_hash", ""),
            world_model=data.get("world_model"),
            skill_opinions=data.get("skill_opinions"),
            evidence_graph=data.get("evidence_graph"),
            health_scores=data.get("health_scores"),
            weight_distribution=data.get("weight_distribution"),
            council_verdict=data.get("council_verdict"),
            meta_verdict=data.get("meta_verdict"),
            policy_verdict=data.get("policy_verdict"),
            working_memory=working_memory,
            decision_trace=decision_trace,
        )

    @staticmethod
    def from_json(json_str: str) -> "DecisionContext":
        return DecisionContext.from_dict(json.loads(json_str))


@dataclass(frozen=True)
class DecisionResult:
    decision: DecisionStatus
    confidence: float
    decision_score: float
    uncertainty: float
    reasoning: List[str] = field(default_factory=list)
    blocking_reasons: List[str] = field(default_factory=list)
    supporting_reasons: List[str] = field(default_factory=list)
    evidence_used: List[str] = field(default_factory=list)
    modules_consulted: List[str] = field(default_factory=list)
    trace_hash: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    version_arch: str = "V10.0" # As specified in the prompt
    version_contracts: str = "V10.0" # As specified in the prompt

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["decision"] = self.decision.value # Serialize Enum member
        d["created_at"] = self.created_at.isoformat()
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, default=str)

    @staticmethod
    def from_dict(data: Dict) -> "DecisionResult":
        # Placeholder deserialization
        decision_val = data.get("decision")
        decision_status = DecisionStatus(decision_val) if decision_val in DecisionStatus._member_map_ else DecisionStatus.HOLD # Default to HOLD if invalid
        
        ts = data.get("created_at")
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)

        return DecisionResult(
            decision=decision_status,
            confidence=data.get("confidence", 0.0),
            decision_score=data.get("decision_score", 0.0),
            uncertainty=data.get("uncertainty", 1.0),
            reasoning=data.get("reasoning", []),
            blocking_reasons=data.get("blocking_reasons", []),
            supporting_reasons=data.get("supporting_reasons", []),
            evidence_used=data.get("evidence_used", []),
            modules_consulted=data.get("modules_consulted", []),
            trace_hash=data.get("trace_hash", ""),
            created_at=ts,
            version_arch=data.get("version_arch", "V10.0"),
            version_contracts=data.get("version_contracts", "V10.0"),
        )

    @staticmethod
    def from_json(json_str: str) -> "DecisionResult":
        return DecisionResult.from_dict(json.loads(json_str))
