import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, List


@dataclass(frozen=True)
class PolicyVerdict:
    allowed: bool
    decision: str
    compliance_score: float
    violated_rules: List[str]
    warnings: List[str]
    recommendations: List[str]
    policy_hash: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["created_at"] = self.created_at.isoformat()
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @staticmethod
    def from_dict(data: Dict) -> "PolicyVerdict":
        ca = data.get("created_at", datetime.now(timezone.utc))
        if isinstance(ca, str):
            ca = datetime.fromisoformat(ca)
        return PolicyVerdict(
            allowed=data["allowed"],
            decision=data["decision"],
            compliance_score=data["compliance_score"],
            violated_rules=data.get("violated_rules", []),
            warnings=data.get("warnings", []),
            recommendations=data.get("recommendations", []),
            policy_hash=data.get("policy_hash", ""),
            created_at=ca,
        )

    @staticmethod
    def from_json(json_str: str) -> "PolicyVerdict":
        return PolicyVerdict.from_dict(json.loads(json_str))

    @staticmethod
    def compute_hash(verdict: "PolicyVerdict") -> str:
        raw = (
            f"{verdict.allowed}|{verdict.decision}|{verdict.compliance_score}|"
            f"{sorted(verdict.violated_rules)}|{sorted(verdict.warnings)}|"
            f"{sorted(verdict.recommendations)}"
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
