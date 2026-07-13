import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, List


@dataclass(frozen=True)
class CouncilVerdict:
    consensus_score: float
    global_confidence: float
    global_risk: float
    global_probability: float
    evidence_quality: float
    evidence_consistency: float
    agreement_level: float
    disagreement_level: float
    participating_skills: List[str]
    conflicting_skills: List[str]
    supporting_clusters: List[str]
    conflicting_clusters: List[str]
    strongest_evidence: List[str]
    weakest_evidence: List[str]
    summary: str
    council_hash: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["created_at"] = self.created_at.isoformat()
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @staticmethod
    def from_dict(data: Dict) -> "CouncilVerdict":
        ca = data.get("created_at", datetime.now(timezone.utc))
        if isinstance(ca, str):
            ca = datetime.fromisoformat(ca)
        return CouncilVerdict(
            consensus_score=data["consensus_score"],
            global_confidence=data["global_confidence"],
            global_risk=data["global_risk"],
            global_probability=data["global_probability"],
            evidence_quality=data["evidence_quality"],
            evidence_consistency=data["evidence_consistency"],
            agreement_level=data["agreement_level"],
            disagreement_level=data["disagreement_level"],
            participating_skills=data.get("participating_skills", []),
            conflicting_skills=data.get("conflicting_skills", []),
            supporting_clusters=data.get("supporting_clusters", []),
            conflicting_clusters=data.get("conflicting_clusters", []),
            strongest_evidence=data.get("strongest_evidence", []),
            weakest_evidence=data.get("weakest_evidence", []),
            summary=data.get("summary", ""),
            council_hash=data.get("council_hash", ""),
            created_at=ca,
        )

    @staticmethod
    def from_json(json_str: str) -> "CouncilVerdict":
        return CouncilVerdict.from_dict(json.loads(json_str))

    @staticmethod
    def compute_hash(verdict: "CouncilVerdict") -> str:
        raw = (
            f"{verdict.consensus_score}|{verdict.global_confidence}|"
            f"{verdict.global_risk}|{verdict.global_probability}|"
            f"{verdict.evidence_quality}|{verdict.evidence_consistency}|"
            f"{verdict.agreement_level}|{verdict.disagreement_level}|"
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
