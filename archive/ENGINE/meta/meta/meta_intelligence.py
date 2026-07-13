import hashlib
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from CORE.events.event_bus import EventBus
from CORE.events.events import Event, EventTypes
from ENGINE.council.council_types import CouncilVerdict
from ENGINE.council.evidence_types import EvidenceGraph
from ENGINE.council.health_types import HealthScore
from ENGINE.council.weight_types import WeightDistribution
from ENGINE.meta.meta_types import MetaVerdict
from ENGINE.meta.meta_config import (
    CONSENSUS_MIN, QUALITY_MIN, CONSISTENCY_MIN,
    CONFIDENCE_MIN, HEALTH_MIN, MAX_CONFLICTS,
    UNCERTAINTY_HIGH, UNCERTAINTY_MODERATE,
    CONFIDENCE_HIGH, CONFIDENCE_MODERATE,
)
from ENGINE.world.world_types import WorldModel

log = logging.getLogger(__name__)


class MetaIntelligence:

    def __init__(self, event_bus: Optional[EventBus] = None):
        self._event_bus = event_bus

    def evaluate(
        self,
        council_verdict: Optional[CouncilVerdict],
        world_model: Optional[WorldModel],
        weight_distribution: Optional[WeightDistribution],
        health_scores: Dict[str, HealthScore],
        evidence_graph: Optional[EvidenceGraph],
    ) -> MetaVerdict:
        blocking_reasons: List[str] = []
        recommendations: List[str] = []

        consensus = self._extract_consensus(council_verdict)
        quality = self._extract_quality(council_verdict, evidence_graph)
        consistency = self._extract_consistency(council_verdict, evidence_graph)
        global_conf = self._extract_confidence(council_verdict)
        conflicts = self._extract_conflicts(council_verdict, evidence_graph)
        avg_health = self._average_health(health_scores)
        reasoning = self._reasoning_score(
            consensus, quality, consistency, global_conf, avg_health,
        )
        information_quality = self._information_quality(council_verdict, evidence_graph)
        uncertainty = self._uncertainty(
            consensus, quality, consistency, global_conf, avg_health, conflicts,
        )

        self._check_consensus(consensus, blocking_reasons, recommendations)
        self._check_quality(quality, blocking_reasons, recommendations)
        self._check_consistency(consistency, blocking_reasons, recommendations)
        self._check_confidence(global_conf, blocking_reasons, recommendations)
        self._check_health(avg_health, blocking_reasons, recommendations)
        self._check_conflicts(conflicts, blocking_reasons, recommendations)
        self._check_world_model(world_model, blocking_reasons, recommendations)
        self._check_reasoning(reasoning, blocking_reasons, recommendations)

        proceed = len(blocking_reasons) == 0
        decision = "PROCEED" if proceed else "HOLD"
        meta_conf = self._meta_confidence(
            consensus, quality, consistency, global_conf,
            avg_health, reasoning, proceed,
        )

        verdict = MetaVerdict(
            proceed=proceed,
            decision=decision,
            confidence=round(meta_conf, 4),
            reasoning_score=round(reasoning, 4),
            information_quality=round(information_quality, 4),
            uncertainty=round(uncertainty, 4),
            detected_conflicts=conflicts,
            blocking_reasons=blocking_reasons,
            recommendations=recommendations,
            meta_hash="",
        )

        final = MetaVerdict(
            proceed=verdict.proceed,
            decision=verdict.decision,
            confidence=verdict.confidence,
            reasoning_score=verdict.reasoning_score,
            information_quality=verdict.information_quality,
            uncertainty=verdict.uncertainty,
            detected_conflicts=verdict.detected_conflicts,
            blocking_reasons=verdict.blocking_reasons,
            recommendations=verdict.recommendations,
            meta_hash=MetaVerdict.compute_hash(verdict),
            created_at=verdict.created_at,
        )

        self._publish(final)
        return final

    def _extract_consensus(self, verdict: Optional[CouncilVerdict]) -> float:
        return verdict.consensus_score if verdict else 0.0

    def _extract_quality(
        self, verdict: Optional[CouncilVerdict],
        graph: Optional[EvidenceGraph],
    ) -> float:
        if verdict and verdict.evidence_quality > 0:
            return verdict.evidence_quality
        return graph.quality if graph else 0.0

    def _extract_consistency(
        self, verdict: Optional[CouncilVerdict],
        graph: Optional[EvidenceGraph],
    ) -> float:
        if verdict and verdict.evidence_consistency > 0:
            return verdict.evidence_consistency
        return graph.consistency if graph else 0.0

    @staticmethod
    def _extract_confidence(verdict: Optional[CouncilVerdict]) -> float:
        return verdict.global_confidence if verdict else 0.0

    @staticmethod
    def _extract_conflicts(
        verdict: Optional[CouncilVerdict],
        graph: Optional[EvidenceGraph],
    ) -> List[str]:
        if verdict and verdict.conflicting_skills:
            return verdict.conflicting_skills
        if graph and graph.contradictions:
            return [c.description for c in graph.contradictions]
        return []

    @staticmethod
    def _average_health(health_scores: Dict[str, HealthScore]) -> float:
        if not health_scores:
            return 0.0
        return sum(h.score for h in health_scores.values()) / len(health_scores)

    def _reasoning_score(
        self,
        consensus: float, quality: float, consistency: float,
        confidence: float, avg_health: float,
    ) -> float:
        return (consensus + quality + consistency + confidence + avg_health) / 5.0

    def _information_quality(
        self,
        verdict: Optional[CouncilVerdict],
        graph: Optional[EvidenceGraph],
    ) -> float:
        quality = self._extract_quality(verdict, graph)
        consistency = self._extract_consistency(verdict, graph)
        return (quality + consistency) / 2.0

    def _uncertainty(
        self,
        consensus: float, quality: float, consistency: float,
        confidence: float, avg_health: float, conflicts: List[str],
    ) -> float:
        conflict_penalty = min(1.0, len(conflicts) / 5.0)
        base = 1.0 - (consensus + quality + consistency + confidence + avg_health) / 5.0
        return min(1.0, max(0.0, base + conflict_penalty * 0.2))

    def _check_consensus(
        self, value: float,
        blocking: List[str], recommendations: List[str],
    ) -> None:
        if value < CONSENSUS_MIN:
            blocking.append("Consensus Score abaixo do minimo")
            recommendations.append("Aguardar aumento do consenso entre especialistas")
        elif value < CONSENSUS_MIN + 0.1:
            recommendations.append("Consenso moderado, monitorar")

    def _check_quality(
        self, value: float,
        blocking: List[str], recommendations: List[str],
    ) -> None:
        if value < QUALITY_MIN:
            blocking.append("Qualidade das evidencias insuficiente")
            recommendations.append("Aguardar evidencias de maior qualidade")
        elif value < QUALITY_MIN + 0.15:
            recommendations.append("Qualidade das evidencias moderada")

    def _check_consistency(
        self, value: float,
        blocking: List[str], recommendations: List[str],
    ) -> None:
        if value < CONSISTENCY_MIN:
            blocking.append("Evidencias inconsistentes")
            recommendations.append("Aguardar evidencias mais consistentes entre as Skills")
        elif value < CONSISTENCY_MIN + 0.2:
            recommendations.append("Consistencia moderada entre evidencias")

    def _check_confidence(
        self, value: float,
        blocking: List[str], recommendations: List[str],
    ) -> None:
        if value < CONFIDENCE_MIN:
            blocking.append("Confianca global insuficiente")
            recommendations.append("Aguardar aumento de confianca nas analises")
        elif value < CONFIDENCE_MIN + 0.15:
            recommendations.append("Confianca global moderada")

    def _check_health(
        self, value: float,
        blocking: List[str], recommendations: List[str],
    ) -> None:
        if value < HEALTH_MIN:
            blocking.append("Health medio das Skills abaixo do esperado")
            recommendations.append("Reavaliar a saude operacional das Skills")
        elif value < HEALTH_MIN + 0.2:
            recommendations.append("Health medio das Skills em nivel aceitavel")

    def _check_conflicts(
        self, conflicts: List[str],
        blocking: List[str], recommendations: List[str],
    ) -> None:
        if len(conflicts) > MAX_CONFLICTS:
            blocking.append("Muitos conflitos entre evidencias")
            recommendations.append("Aguardar resolucao dos conflitos entre Skills")
        elif len(conflicts) > 0:
            recommendations.append("Conflitos detectados, monitorar")

    def _check_world_model(
        self, world_model: Optional[WorldModel],
        blocking: List[str], recommendations: List[str],
    ) -> None:
        if world_model is None:
            blocking.append("World Model ausente")
            recommendations.append("Aguardar World Model disponivel")
        elif not world_model.is_tradeable():
            blocking.append("Ambiente nao operavel segundo World Model")
            recommendations.append("Aguardar mudanca de regime ou melhora do ambiente")
        elif world_model.confidence < 0.30:
            blocking.append("Confianca do World Model insuficiente")
            recommendations.append("Aguardar maior confianca no World Model")

    def _check_reasoning(
        self, value: float,
        blocking: List[str], recommendations: List[str],
    ) -> None:
        if value < 0.20:
            blocking.append("Score de raciocinio muito baixo")
            recommendations.append("Reavaliar apos coleta de mais informacoes")

    def _meta_confidence(
        self,
        consensus: float, quality: float, consistency: float,
        confidence: float, avg_health: float,
        reasoning: float, proceed: bool,
    ) -> float:
        if not proceed:
            return max(0.0, reasoning - 0.1)
        return min(1.0, (
            consensus * 0.25
            + quality * 0.20
            + consistency * 0.15
            + confidence * 0.20
            + avg_health * 0.10
            + reasoning * 0.10
        ))

    def _publish(self, verdict: MetaVerdict) -> None:
        if self._event_bus is None:
            return
        try:
            event_type = (
                EventTypes.META_PROCEED if verdict.proceed
                else EventTypes.META_HOLD
            )
            self._event_bus.publish(Event(
                event_type,
                {"verdict": verdict.to_dict()},
            ))
        except Exception as e:
            log.error("Failed to publish meta event: %s", e)
