import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class EvidenceNode:
    id: str
    evidence_text: str
    source_skills: Tuple[str, ...]
    confidence: float
    risk: float
    probability: float
    occurrences: int
    weight: float


@dataclass(frozen=True)
class EvidenceCluster:
    id: str
    topic: str
    node_ids: Tuple[str, ...]
    evidence_texts: Tuple[str, ...]
    confidence: float
    consistency: float
    weight: float


@dataclass(frozen=True)
class EvidenceConflict:
    source_id: str
    target_id: str
    severity: float
    description: str


@dataclass(frozen=True)
class EvidenceGraph:
    nodes: Tuple[EvidenceNode, ...]
    clusters: Tuple[EvidenceCluster, ...]
    contradictions: Tuple[EvidenceConflict, ...]
    confidence: float
    quality: float
    consistency: float
    graph_hash: str
    num_skills: int
    num_duplicates_removed: int

    def to_dict(self) -> Dict:
        return {
            "nodes": [asdict(n) for n in self.nodes],
            "clusters": [asdict(c) for c in self.clusters],
            "contradictions": [asdict(c) for c in self.contradictions],
            "confidence": self.confidence,
            "quality": self.quality,
            "consistency": self.consistency,
            "graph_hash": self.graph_hash,
            "num_skills": self.num_skills,
            "num_duplicates_removed": self.num_duplicates_removed,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @staticmethod
    def from_dict(data: Dict) -> "EvidenceGraph":
        nodes = tuple(
            EvidenceNode(**n) for n in data["nodes"]
        )
        clusters = tuple(
            EvidenceCluster(
                id=c["id"],
                topic=c["topic"],
                node_ids=tuple(c["node_ids"]),
                evidence_texts=tuple(c["evidence_texts"]),
                confidence=c["confidence"],
                consistency=c["consistency"],
                weight=c["weight"],
            )
            for c in data["clusters"]
        )
        contradictions = tuple(
            EvidenceConflict(**c) for c in data["contradictions"]
        )
        return EvidenceGraph(
            nodes=nodes,
            clusters=clusters,
            contradictions=contradictions,
            confidence=data["confidence"],
            quality=data["quality"],
            consistency=data["consistency"],
            graph_hash=data["graph_hash"],
            num_skills=data["num_skills"],
            num_duplicates_removed=data["num_duplicates_removed"],
        )

    @staticmethod
    def from_json(json_str: str) -> "EvidenceGraph":
        return EvidenceGraph.from_dict(json.loads(json_str))
