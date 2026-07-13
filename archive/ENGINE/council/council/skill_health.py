import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence

from ENGINE.skills.skill_opinion import SkillMetrics
from ENGINE.skills.skill_registry import SkillRegistry
from ENGINE.council.health_types import HealthScore, HealthStatus
from ENGINE.council.health_config import (
    LATENCY_THRESHOLDS,
    EXCELLENT_MIN,
    GOOD_MIN,
    FAIR_MIN,
    DEGRADED_MIN,
    WEIGHT_AVAILABILITY,
    WEIGHT_RELIABILITY,
    WEIGHT_PRECISION,
    WEIGHT_LATENCY,
    WEIGHT_STABILITY,
    PENALTY_TIMEOUT_PER_UNIT,
    PENALTY_ERROR_PER_UNIT,
    PENALTY_MAX,
    REC_LATENCY_HIGH,
    REC_ERRORS,
    REC_PRECISION_LOW,
    REC_ALGORITHM,
    REC_WEIGHT_REDUCE,
    REC_AVAILABILITY_LOW,
    REC_STABILITY_LOW,
)

log = logging.getLogger(__name__)


class HealthScoreCalculator:

    def calculate(
        self,
        skill_name: str,
        metrics: SkillMetrics,
        timeouts: int = 0,
    ) -> HealthScore:
        availability_score = min(1.0, max(0.0, metrics.availability))
        reliability_score = min(1.0, max(0.0, metrics.reliability))
        precision_score = min(1.0, max(0.0, metrics.historical_precision))
        latency_score = self._compute_latency_score(metrics.avg_latency_ms)
        stability = self._compute_stability(metrics)
        error_penalty = self._compute_error_penalty(metrics)
        timeout_penalty = self._compute_timeout_penalty(timeouts)

        base_score = (
            availability_score * WEIGHT_AVAILABILITY
            + reliability_score * WEIGHT_RELIABILITY
            + precision_score * WEIGHT_PRECISION
            + latency_score * WEIGHT_LATENCY
            + stability * WEIGHT_STABILITY
        )

        total_penalty = min(PENALTY_MAX, error_penalty + timeout_penalty)
        final_score = round(max(0.0, base_score * (1.0 - total_penalty)), 4)
        status = self._classify(final_score)
        recommendations = self._generate_recommendations(
            latency_score, metrics, stability,
            error_penalty, timeout_penalty,
        )

        return HealthScore(
            skill_name=skill_name,
            score=final_score,
            availability=round(availability_score, 4),
            reliability=round(reliability_score, 4),
            precision=round(precision_score, 4),
            latency_score=round(latency_score, 4),
            stability=round(stability, 4),
            timeout_penalty=round(timeout_penalty, 4),
            error_penalty=round(error_penalty, 4),
            status=status,
            recommendations=recommendations,
            computed_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _compute_latency_score(avg_latency_ms: float) -> float:
        if avg_latency_ms <= LATENCY_THRESHOLDS["excellent"]:
            return 1.0
        if avg_latency_ms <= LATENCY_THRESHOLDS["good"]:
            return 0.8
        if avg_latency_ms <= LATENCY_THRESHOLDS["fair"]:
            return 0.5
        if avg_latency_ms <= LATENCY_THRESHOLDS["degraded"]:
            return 0.2
        return 0.0

    @staticmethod
    def _compute_stability(metrics: SkillMetrics) -> float:
        if metrics.total_calls == 0:
            return 1.0
        error_rate = metrics.recent_errors / max(1, metrics.total_calls)
        stability = 1.0 - error_rate
        return max(0.0, stability)

    @staticmethod
    def _compute_error_penalty(metrics: SkillMetrics) -> float:
        if metrics.total_calls == 0:
            return 0.0
        penalty = metrics.recent_errors * PENALTY_ERROR_PER_UNIT
        return min(1.0, penalty)

    @staticmethod
    def _compute_timeout_penalty(timeouts: int) -> float:
        if timeouts <= 0:
            return 0.0
        penalty = timeouts * PENALTY_TIMEOUT_PER_UNIT
        return min(1.0, penalty)

    @staticmethod
    def _classify(score: float) -> HealthStatus:
        if score >= EXCELLENT_MIN:
            return HealthStatus.EXCELLENT
        if score >= GOOD_MIN:
            return HealthStatus.GOOD
        if score >= FAIR_MIN:
            return HealthStatus.FAIR
        if score >= DEGRADED_MIN:
            return HealthStatus.DEGRADED
        return HealthStatus.CRITICAL

    @staticmethod
    def _generate_recommendations(
        latency_score: float,
        metrics: SkillMetrics,
        stability: float,
        error_penalty: float,
        timeout_penalty: float,
    ) -> List[str]:
        recs: List[str] = []

        if latency_score < 0.5:
            recs.append(REC_LATENCY_HIGH)

        if error_penalty > 0.1:
            recs.append(REC_ERRORS)

        if metrics.historical_precision < 0.5 and metrics.historical_precision >= 0.0:
            recs.append(REC_PRECISION_LOW)
            recs.append(REC_ALGORITHM)

        if metrics.availability < 0.5:
            recs.append(REC_WEIGHT_REDUCE)
            recs.append(REC_AVAILABILITY_LOW)

        if stability < 0.5:
            recs.append(REC_STABILITY_LOW)

        return recs


class HealthManager:
    def __init__(self, registry: Optional[SkillRegistry] = None):
        self._registry = registry
        self._calculator = HealthScoreCalculator()
        self._cache: Dict[str, HealthScore] = {}

    def set_registry(self, registry: SkillRegistry) -> None:
        self._registry = registry

    def evaluate(
        self,
        skill_name: str,
        metrics: SkillMetrics,
        timeouts: int = 0,
    ) -> HealthScore:
        score = self._calculator.calculate(skill_name, metrics, timeouts)
        self._cache[skill_name] = score
        return score

    def evaluate_all(self, timeouts_map: Optional[Dict[str, int]] = None) -> List[HealthScore]:
        if self._registry is None:
            log.warning("No registry set — cannot evaluate all skills")
            return []

        timeouts_map = timeouts_map or {}
        results: List[HealthScore] = []

        for reg in self._registry.get_all_registrations():
            skill = self._registry.get_skill(reg.name)
            if skill is None:
                continue
            metrics = getattr(skill, "metrics", SkillMetrics())
            timeouts = timeouts_map.get(reg.name, 0)
            score = self.evaluate(reg.name, metrics, timeouts)
            results.append(score)

        return results

    def get_latest(self, skill_name: str) -> Optional[HealthScore]:
        return self._cache.get(skill_name)

    def clear_cache(self) -> None:
        self._cache.clear()
