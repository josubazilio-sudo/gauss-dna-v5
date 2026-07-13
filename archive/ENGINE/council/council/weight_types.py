import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, List


@dataclass(frozen=True)
class SkillWeight:
    skill_name: str
    final_weight: float
    base_weight: float
    regime_multiplier: float
    health_multiplier: float
    performance_multiplier: float
    confidence_multiplier: float
    specialization_multiplier: float
    normalization_factor: float
    reasons: List[str]
    computed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict:
        return {
            "skill_name": self.skill_name,
            "final_weight": self.final_weight,
            "base_weight": self.base_weight,
            "regime_multiplier": self.regime_multiplier,
            "health_multiplier": self.health_multiplier,
            "performance_multiplier": self.performance_multiplier,
            "confidence_multiplier": self.confidence_multiplier,
            "specialization_multiplier": self.specialization_multiplier,
            "normalization_factor": self.normalization_factor,
            "reasons": self.reasons,
            "computed_at": self.computed_at.isoformat(),
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


@dataclass(frozen=True)
class WeightDistribution:
    weights: Dict[str, SkillWeight]
    total_weight: float
    normalized: bool
    distribution_hash: str
    computed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict:
        return {
            "weights": {k: v.to_dict() for k, v in self.weights.items()},
            "total_weight": self.total_weight,
            "normalized": self.normalized,
            "distribution_hash": self.distribution_hash,
            "computed_at": self.computed_at.isoformat(),
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @staticmethod
    def from_dict(data: Dict) -> "WeightDistribution":
        weights = {}
        for k, v in data["weights"].items():
            if isinstance(v, dict):
                if isinstance(v.get("computed_at"), str):
                    ca = datetime.fromisoformat(v["computed_at"])
                else:
                    ca = v.get("computed_at", datetime.now(timezone.utc))
                weights[k] = SkillWeight(
                    skill_name=v["skill_name"],
                    final_weight=v["final_weight"],
                    base_weight=v["base_weight"],
                    regime_multiplier=v["regime_multiplier"],
                    health_multiplier=v["health_multiplier"],
                    performance_multiplier=v["performance_multiplier"],
                    confidence_multiplier=v["confidence_multiplier"],
                    specialization_multiplier=v["specialization_multiplier"],
                    normalization_factor=v["normalization_factor"],
                    reasons=v.get("reasons", []),
                    computed_at=ca,
                )
        ca = data.get("computed_at", datetime.now(timezone.utc))
        if isinstance(ca, str):
            ca = datetime.fromisoformat(ca)
        return WeightDistribution(
            weights=weights,
            total_weight=data["total_weight"],
            normalized=data["normalized"],
            distribution_hash=data["distribution_hash"],
            computed_at=ca,
        )

    @staticmethod
    def from_json(json_str: str) -> "WeightDistribution":
        return WeightDistribution.from_dict(json.loads(json_str))

    @staticmethod
    def compute_hash(dist: "WeightDistribution") -> str:
        parts = []
        for name in sorted(dist.weights.keys()):
            sw = dist.weights[name]
            parts.append(f"{name}|{sw.final_weight}|{sw.base_weight}|"
                         f"{sw.regime_multiplier}|{sw.health_multiplier}|"
                         f"{sw.performance_multiplier}|{sw.confidence_multiplier}|"
                         f"{sw.specialization_multiplier}")
        canonical = "||".join(parts)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
