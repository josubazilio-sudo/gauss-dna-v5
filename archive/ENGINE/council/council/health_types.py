import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List


class HealthStatus(Enum):
    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"
    FAIR = "FAIR"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class HealthScore:
    skill_name: str
    score: float
    availability: float
    reliability: float
    precision: float
    latency_score: float
    stability: float
    timeout_penalty: float
    error_penalty: float
    status: HealthStatus
    recommendations: List[str]
    computed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict:
        return {
            "skill_name": self.skill_name,
            "score": self.score,
            "availability": self.availability,
            "reliability": self.reliability,
            "precision": self.precision,
            "latency_score": self.latency_score,
            "stability": self.stability,
            "timeout_penalty": self.timeout_penalty,
            "error_penalty": self.error_penalty,
            "status": self.status.value,
            "recommendations": self.recommendations,
            "computed_at": self.computed_at.isoformat(),
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @staticmethod
    def from_dict(data: Dict) -> "HealthScore":
        if isinstance(data.get("computed_at"), str):
            computed_at = datetime.fromisoformat(data["computed_at"])
        else:
            computed_at = data.get("computed_at", datetime.now(timezone.utc))

        return HealthScore(
            skill_name=data["skill_name"],
            score=data["score"],
            availability=data["availability"],
            reliability=data["reliability"],
            precision=data["precision"],
            latency_score=data["latency_score"],
            stability=data["stability"],
            timeout_penalty=data["timeout_penalty"],
            error_penalty=data["error_penalty"],
            status=HealthStatus(data["status"]),
            recommendations=data.get("recommendations", []),
            computed_at=computed_at,
        )

    @staticmethod
    def from_json(json_str: str) -> "HealthScore":
        return HealthScore.from_dict(json.loads(json_str))

    @staticmethod
    def compute_hash(score: "HealthScore") -> str:
        canonical = (
            f"{score.skill_name}|{score.score}|{score.availability}|"
            f"{score.reliability}|{score.precision}|{score.latency_score}|"
            f"{score.stability}|{score.timeout_penalty}|{score.error_penalty}|"
            f"{score.status.value}"
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
