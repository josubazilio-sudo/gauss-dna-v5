import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, List


@dataclass(frozen=True)
class MetaVerdict:
    proceed: bool
    decision: str
    confidence: float
    reasoning_score: float
    information_quality: float
    uncertainty: float
    detected_conflicts: List[str]
    blocking_reasons: List[str]
    recommendations: List[str]
    meta_hash: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["created_at"] = self.created_at.isoformat()
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @staticmethod
    def from_dict(data: Dict) -> "MetaVerdict":
        ca = data.get("created_at", datetime.now(timezone.utc))
        if isinstance(ca, str):
            ca = datetime.fromisoformat(ca)
        return MetaVerdict(
            proceed=data["proceed"],
            decision=data["decision"],
            confidence=data["confidence"],
            reasoning_score=data["reasoning_score"],
            information_quality=data["information_quality"],
            uncertainty=data["uncertainty"],
            detected_conflicts=data.get("detected_conflicts", []),
            blocking_reasons=data.get("blocking_reasons", []),
            recommendations=data.get("recommendations", []),
            meta_hash=data.get("meta_hash", ""),
            created_at=ca,
        )

    @staticmethod
    def from_json(json_str: str) -> "MetaVerdict":
        return MetaVerdict.from_dict(json.loads(json_str))

    @staticmethod
    def compute_hash(verdict: "MetaVerdict") -> str:
        raw = (
            f"{verdict.proceed}|{verdict.decision}|{verdict.confidence}|"
            f"{verdict.reasoning_score}|{verdict.information_quality}|"
            f"{verdict.uncertainty}|{sorted(verdict.detected_conflicts)}|"
            f"{sorted(verdict.blocking_reasons)}|{sorted(verdict.recommendations)}"
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
