import hashlib
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence

from CORE.events.event_bus import EventBus
from CORE.events.events import Event, EventTypes
from ENGINE.world.world_types import WorldModel
from ENGINE.skills.skill_opinion import SkillOpinion
from ENGINE.council.health_types import HealthScore, HealthStatus
from ENGINE.council.evidence_types import EvidenceGraph
from ENGINE.council.weight_types import WeightDistribution
from ENGINE.council.council_types import CouncilVerdict
from ENGINE.council.council_config import (
    W_CONFIDENCE, W_QUALITY, W_CONSISTENCY, W_AGREEMENT, W_RISK_INVERSE,
    HEALTH_ADJUSTMENT,
    HEALTH_EXCELLENT, HEALTH_GOOD, HEALTH_FAIR, HEALTH_DEGRADED,
    CONSENSUS_HIGH, CONSENSUS_MODERATE,
    AGREEMENT_HIGH, AGREEMENT_MODERATE,
    CLUSTER_CONFIDENCE_MIN,
    SUMMARY_MAX_SKILLS, SUMMARY_MAX_EVIDENCE,
)

log = logging.getLogger(__name__)


class SkillConsensusEngine:
    """Consenso ponderado das opinioes de Skills (arquitetura V10/Council).

    Nao confundir com ENGINE.consensus.consensus_engine.ConsensusEngine, que
    calcula consenso multi-timeframe do scanner de producao — sao dois
    conceitos diferentes que compartilhavam o mesmo nome de classe."""

    def __init__(self, event_bus: Optional[EventBus] = None):
        self._event_bus = event_bus

    def evaluate(
        self,
        opinions: Sequence[SkillOpinion],
        evidence_graph: EvidenceGraph,
        weight_distribution: WeightDistribution,
        health_map: Dict[str, HealthScore],
        world_model: Optional[WorldModel] = None,
    ) -> CouncilVerdict:
        if not opinions:
            return self._empty_verdict("Nenhuma Skill participou da analise")

        global_conf = self._weighted_confidence(opinions, weight_distribution, health_map)
        global_risk = self._weighted_risk(opinions, weight_distribution, health_map)
        global_prob = self._weighted_probability(opinions, weight_distribution, health_map)
        evidence_quality = evidence_graph.quality
        evidence_consistency = evidence_graph.consistency
        agreement = self._agreement_level(evidence_graph, opinions)
        disagreement = self._disagreement_level(evidence_graph, evidence_consistency)

        consensus = self._consensus_score(
            global_conf, evidence_quality, evidence_consistency,
            agreement, global_risk,
        )

        participating = self._participating_skills(opinions)
        conflicting = self._conflicting_skills(evidence_graph)
        sup_clusters = self._supporting_clusters(evidence_graph)
        conf_clusters = self._conflicting_clusters(evidence_graph)
        strongest = self._strongest_evidence(evidence_graph)
        weakest = self._weakest_evidence(evidence_graph)
        summary = self._build_summary(
            opinions, evidence_graph, consensus, agreement, disagreement,
        )

        verdict = CouncilVerdict(
            consensus_score=round(consensus, 4),
            global_confidence=round(global_conf, 4),
            global_risk=round(global_risk, 4),
            global_probability=round(global_prob, 4),
            evidence_quality=round(evidence_quality, 4),
            evidence_consistency=round(evidence_consistency, 4),
            agreement_level=round(agreement, 4),
            disagreement_level=round(disagreement, 4),
            participating_skills=participating,
            conflicting_skills=conflicting,
            supporting_clusters=sup_clusters,
            conflicting_clusters=conf_clusters,
            strongest_evidence=strongest,
            weakest_evidence=weakest,
            summary=summary,
            council_hash="",
        )

        final = CouncilVerdict(
            consensus_score=verdict.consensus_score,
            global_confidence=verdict.global_confidence,
            global_risk=verdict.global_risk,
            global_probability=verdict.global_probability,
            evidence_quality=verdict.evidence_quality,
            evidence_consistency=verdict.evidence_consistency,
            agreement_level=verdict.agreement_level,
            disagreement_level=verdict.disagreement_level,
            participating_skills=verdict.participating_skills,
            conflicting_skills=verdict.conflicting_skills,
            supporting_clusters=verdict.supporting_clusters,
            conflicting_clusters=verdict.conflicting_clusters,
            strongest_evidence=verdict.strongest_evidence,
            weakest_evidence=verdict.weakest_evidence,
            summary=verdict.summary,
            council_hash=CouncilVerdict.compute_hash(verdict),
            created_at=verdict.created_at,
        )

        self._publish(final)
        return final

    def _weighted_confidence(
        self,
        opinions: Sequence[SkillOpinion],
        weights: WeightDistribution,
        health_map: Dict[str, HealthScore],
    ) -> float:
        total_weight = 0.0
        weighted_sum = 0.0
        for op in opinions:
            w = self._effective_weight(op.skill_name, weights, health_map)
            weighted_sum += op.confidence * w
            total_weight += w
        return weighted_sum / total_weight if total_weight > 0 else 0.0

    def _weighted_risk(
        self,
        opinions: Sequence[SkillOpinion],
        weights: WeightDistribution,
        health_map: Dict[str, HealthScore],
    ) -> float:
        total_weight = 0.0
        weighted_sum = 0.0
        for op in opinions:
            w = self._effective_weight(op.skill_name, weights, health_map)
            weighted_sum += op.risk * w
            total_weight += w
        return weighted_sum / total_weight if total_weight > 0 else 0.0

    def _weighted_probability(
        self,
        opinions: Sequence[SkillOpinion],
        weights: WeightDistribution,
        health_map: Dict[str, HealthScore],
    ) -> float:
        total_weight = 0.0
        weighted_sum = 0.0
        for op in opinions:
            w = self._effective_weight(op.skill_name, weights, health_map)
            weighted_sum += op.probability * w
            total_weight += w
        return weighted_sum / total_weight if total_weight > 0 else 0.0

    @staticmethod
    def _effective_weight(
        skill_name: str,
        weights: WeightDistribution,
        health_map: Dict[str, HealthScore],
    ) -> float:
        w = weights.weights.get(skill_name)
        base = w.final_weight if w else 1.0 / max(1, len(weights.weights))

        health = health_map.get(skill_name)
        if health is None:
            adj = 1.0
        else:
            score = health.score
            if score >= HEALTH_EXCELLENT:
                adj = HEALTH_ADJUSTMENT["excellent"]
            elif score >= HEALTH_GOOD:
                adj = HEALTH_ADJUSTMENT["good"]
            elif score >= HEALTH_FAIR:
                adj = HEALTH_ADJUSTMENT["fair"]
            elif score >= HEALTH_DEGRADED:
                adj = HEALTH_ADJUSTMENT["degraded"]
            else:
                adj = HEALTH_ADJUSTMENT["critical"]

        return base * adj

    @staticmethod
    def _agreement_level(
        graph: EvidenceGraph,
        opinions: Sequence[SkillOpinion],
    ) -> float:
        if not opinions or len(opinions) < 2:
            return 1.0

        base = graph.consistency

        if not graph.contradictions:
            base = max(base, 0.85)

        return min(1.0, max(0.0, base))

    @staticmethod
    def _disagreement_level(
        graph: EvidenceGraph,
        consistency: float,
    ) -> float:
        if consistency >= 0.9:
            return 0.0
        if graph.contradictions:
            return round(min(1.0, 1.0 - consistency + 0.1 * len(graph.contradictions)), 4)
        return round(max(0.0, 1.0 - consistency - 0.1), 4)

    @staticmethod
    def _consensus_score(
        global_conf: float, quality: float, consistency: float,
        agreement: float, global_risk: float,
    ) -> float:
        return (
            global_conf * W_CONFIDENCE
            + quality * W_QUALITY
            + consistency * W_CONSISTENCY
            + agreement * W_AGREEMENT
            + (1.0 - global_risk) * W_RISK_INVERSE
        )

    @staticmethod
    def _participating_skills(opinions: Sequence[SkillOpinion]) -> List[str]:
        return [o.skill_name for o in opinions if o.success]

    @staticmethod
    def _conflicting_skills(graph: EvidenceGraph) -> List[str]:
        if not graph.contradictions:
            return []
        node_map = {n.id: n for n in graph.nodes}
        skills: set = set()
        for c in graph.contradictions:
            sn = node_map.get(c.source_id)
            tn = node_map.get(c.target_id)
            if sn:
                for s in sn.source_skills:
                    skills.add(s)
            if tn:
                for s in tn.source_skills:
                    skills.add(s)
        return sorted(skills)

    @staticmethod
    def _supporting_clusters(graph: EvidenceGraph) -> List[str]:
        return [c.topic for c in graph.clusters if c.confidence >= CLUSTER_CONFIDENCE_MIN]

    @staticmethod
    def _conflicting_clusters(graph: EvidenceGraph) -> List[str]:
        if not graph.contradictions or not graph.clusters:
            return []
        cluster_map = {}
        for c in graph.clusters:
            for nid in c.node_ids:
                cluster_map[nid] = c.topic
        topics: set = set()
        for c in graph.contradictions:
            if c.source_id in cluster_map:
                topics.add(cluster_map[c.source_id])
            if c.target_id in cluster_map:
                topics.add(cluster_map[c.target_id])
        return sorted(topics)

    @staticmethod
    def _strongest_evidence(graph: EvidenceGraph) -> List[str]:
        scored = [(n.confidence * n.weight, n.evidence_text) for n in graph.nodes]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [text for _, text in scored[:SUMMARY_MAX_EVIDENCE]]

    @staticmethod
    def _weakest_evidence(graph: EvidenceGraph) -> List[str]:
        scored = [(n.confidence * n.weight, n.evidence_text) for n in graph.nodes]
        scored.sort(key=lambda x: x[0])
        return [text for _, text in scored[:SUMMARY_MAX_EVIDENCE]]

    @staticmethod
    def _build_summary(
        opinions: Sequence[SkillOpinion],
        graph: EvidenceGraph,
        consensus: float, agreement: float, disagreement: float,
    ) -> str:
        n_skills = len(opinions)
        n_clusters = len(graph.clusters)
        n_conflicts = len(graph.contradictions)

        if consensus >= CONSENSUS_HIGH:
            qual = "ALTO"
        elif consensus >= CONSENSUS_MODERATE:
            qual = "MODERADO"
        else:
            qual = "BAIXO"

        parts = [
            f"Consenso {qual} (score: {consensus:.3f}).",
            f"{n_skills} skill(s) participaram.",
            f"Acordo: {agreement:.2f}, Desacordo: {disagreement:.2f}.",
        ]
        if n_clusters > 0:
            parts.append(f"{n_clusters} cluster(s) de evidencia.")
        if n_conflicts > 0:
            parts.append(f"{n_conflicts} conflito(s) detectado(s).")
        if graph.quality > 0:
            parts.append(f"Qualidade das evidencias: {graph.quality:.2f}.")

        return " ".join(parts)

    def _publish(self, verdict: CouncilVerdict) -> None:
        if self._event_bus is None:
            return
        try:
            self._event_bus.publish(Event(
                EventTypes.COUNCIL_VERDICT_READY,
                {"verdict": verdict.to_dict()},
            ))
        except Exception as e:
            log.error("Failed to publish council.verdict_ready: %s", e)

    @staticmethod
    def _empty_verdict(reason: str) -> CouncilVerdict:
        v = CouncilVerdict(
            consensus_score=0.0, global_confidence=0.0, global_risk=1.0,
            global_probability=0.0, evidence_quality=0.0,
            evidence_consistency=0.0, agreement_level=0.0,
            disagreement_level=0.0, participating_skills=[],
            conflicting_skills=[], supporting_clusters=[],
            conflicting_clusters=[], strongest_evidence=[],
            weakest_evidence=[], summary=reason, council_hash="",
        )
        return CouncilVerdict(
            consensus_score=v.consensus_score, global_confidence=v.global_confidence,
            global_risk=v.global_risk, global_probability=v.global_probability,
            evidence_quality=v.evidence_quality,
            evidence_consistency=v.evidence_consistency,
            agreement_level=v.agreement_level, disagreement_level=v.disagreement_level,
            participating_skills=v.participating_skills,
            conflicting_skills=v.conflicting_skills,
            supporting_clusters=v.supporting_clusters,
            conflicting_clusters=v.conflicting_clusters,
            strongest_evidence=v.strongest_evidence,
            weakest_evidence=v.weakest_evidence,
            summary=v.summary, council_hash=CouncilVerdict.compute_hash(v),
            created_at=v.created_at,
        )
