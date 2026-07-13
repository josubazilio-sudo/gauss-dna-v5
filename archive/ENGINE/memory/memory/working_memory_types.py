import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ENGINE.council.council_types import CouncilVerdict
from ENGINE.council.evidence_types import EvidenceGraph
from ENGINE.council.health_types import HealthScore
from ENGINE.council.weight_types import WeightDistribution
from ENGINE.meta.meta_types import MetaVerdict
from ENGINE.policy.policy_types import PolicyVerdict
from ENGINE.market.market_types import MarketContext
from ENGINE.skills.skill_opinion import SkillOpinion
from ENGINE.world.world_types import WorldModel


@dataclass(frozen=True)
class WorkingMemory:
    cycle_id: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    market_context: Optional[MarketContext] = None
    world_model: Optional[WorldModel] = None
    skill_opinions: Optional[List[SkillOpinion]] = None
    evidence_graph: Optional[EvidenceGraph] = None
    health_scores: Optional[Dict[str, HealthScore]] = None
    weight_distribution: Optional[WeightDistribution] = None
    council_verdict: Optional[CouncilVerdict] = None
    meta_verdict: Optional[MetaVerdict] = None
    policy_verdict: Optional[PolicyVerdict] = None

    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "cycle_id": self.cycle_id,
            "timestamp": self.timestamp.isoformat(),
            "market_context": None,
            "world_model": None,
            "skill_opinions": None,
            "evidence_graph": None,
            "health_scores": None,
            "weight_distribution": None,
            "council_verdict": None,
            "meta_verdict": None,
            "policy_verdict": None,
            "metadata": dict(self.metadata),
        }
        if self.market_context is not None:
            d["market_context"] = self.market_context.to_dict()
        if self.world_model is not None:
            d["world_model"] = self.world_model.to_dict()
        if self.skill_opinions is not None:
            d["skill_opinions"] = [asdict(o) for o in self.skill_opinions]
        if self.evidence_graph is not None:
            d["evidence_graph"] = self.evidence_graph.to_dict()
        if self.health_scores is not None:
            d["health_scores"] = {k: v.to_dict() for k, v in self.health_scores.items()}
        if self.weight_distribution is not None:
            d["weight_distribution"] = self.weight_distribution.to_dict()
        if self.council_verdict is not None:
            d["council_verdict"] = self.council_verdict.to_dict()
        if self.meta_verdict is not None:
            d["meta_verdict"] = self.meta_verdict.to_dict()
        if self.policy_verdict is not None:
            d["policy_verdict"] = self.policy_verdict.to_dict()
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, default=str)

    @staticmethod
    def compute_hash(wm: "WorkingMemory") -> str:
        def _obj_hash(obj) -> str:
            if obj is None:
                return "none"
            if hasattr(obj, "to_dict"):
                return hashlib.sha256(
                    json.dumps(obj.to_dict(), sort_keys=True, default=str).encode("utf-8"),
                ).hexdigest()[:16]
            return hashlib.sha256(str(obj).encode("utf-8")).hexdigest()[:16]

        canonical = (
            f"{wm.cycle_id}|{_obj_hash(wm.market_context)}|"
            f"{_obj_hash(wm.world_model)}|"
            f"{len(wm.skill_opinions) if wm.skill_opinions else -1}|"
            f"{wm.evidence_graph.graph_hash if wm.evidence_graph else 'none'}|"
            f"{len(wm.health_scores) if wm.health_scores else -1}|"
            f"{wm.weight_distribution.distribution_hash if wm.weight_distribution else 'none'}|"
            f"{wm.council_verdict.council_hash if wm.council_verdict else 'none'}|"
            f"{wm.meta_verdict.meta_hash if wm.meta_verdict else 'none'}|"
            f"{wm.policy_verdict.policy_hash if wm.policy_verdict else 'none'}"
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
