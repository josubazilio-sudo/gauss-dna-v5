import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence, Set

from ENGINE.world.world_types import WorldModel, MarketState
from ENGINE.skills.skill_opinion import SkillOpinion, SkillMetrics
from ENGINE.skills.skill_registry import SkillRegistry, SkillRegistration
from ENGINE.council.health_types import HealthScore, HealthStatus
from ENGINE.council.weight_types import SkillWeight, WeightDistribution
from ENGINE.council.weight_config import (
    BASE_WEIGHT_DEFAULT,
    MAX_WEIGHT_PER_SKILL,
    NORMALIZE_TARGET,
    REGIME_MULTIPLIERS,
    HEALTH_MULTIPLIERS,
    PERFORMANCE_MULTIPLIERS,
    PERFORMANCE_THRESHOLD_HIGH,
    PERFORMANCE_THRESHOLD_LOW,
    CONFIDENCE_MULTIPLIERS,
    CONFIDENCE_THRESHOLD_HIGH,
    CONFIDENCE_THRESHOLD_LOW,
    SPECIALIZATION_KEYWORDS,
    HEALTH_EXCELLENT,
    HEALTH_GOOD,
    HEALTH_FAIR,
    HEALTH_DEGRADED,
    REGIME_CONFIDENCE_MIN,
)

log = logging.getLogger(__name__)


def _make_sw(
    sw: SkillWeight, final_weight: float, norm_factor: float,
    reasons: List[str],
) -> SkillWeight:
    return SkillWeight(
        skill_name=sw.skill_name,
        final_weight=round(final_weight, 6),
        base_weight=sw.base_weight,
        regime_multiplier=sw.regime_multiplier,
        health_multiplier=sw.health_multiplier,
        performance_multiplier=sw.performance_multiplier,
        confidence_multiplier=sw.confidence_multiplier,
        specialization_multiplier=sw.specialization_multiplier,
        normalization_factor=round(norm_factor, 4),
        reasons=reasons,
    )


def _make_equal_distribution(
    raw_weights: List[tuple], reason: str,
) -> Dict[str, SkillWeight]:
    equal = NORMALIZE_TARGET / len(raw_weights)
    result = {}
    for name, sw in raw_weights:
        nf = equal / sw.final_weight if sw.final_weight > 0 else 1.0
        result[name] = _make_sw(sw, equal, nf, sw.reasons + [reason])
    return result


class DynamicWeightCalculator:

    def calculate_all(
        self,
        opinions: Sequence[SkillOpinion],
        registrations: Dict[str, SkillRegistration],
        metrics_map: Dict[str, SkillMetrics],
        health_map: Dict[str, HealthScore],
        world_model: Optional[WorldModel] = None,
    ) -> WeightDistribution:
        skill_names = {o.skill_name for o in opinions}
        if not skill_names:
            return self._empty()

        regime = self._infer_regime(world_model)
        reasons: List[str] = [f"Regime: {regime}"]

        raw_weights: List[tuple] = []

        for opinion in opinions:
            name = opinion.skill_name
            reg = registrations.get(name)
            metrics = metrics_map.get(name, SkillMetrics())
            health = health_map.get(name)

            sw = self._calculate(
                skill_name=name,
                opinion=opinion,
                registration=reg,
                metrics=metrics,
                health=health,
                regime=regime,
            )
            raw_weights.append((name, sw))

        normalized = self._normalize(raw_weights)
        dist_hash = self._compute_hash(normalized)

        return WeightDistribution(
            weights={name: sw for name, sw in normalized.items()},
            total_weight=round(sum(sw.final_weight for sw in normalized.values()), 4),
            normalized=True,
            distribution_hash=dist_hash,
        )

    def _calculate(
        self,
        skill_name: str,
        opinion: SkillOpinion,
        registration: Optional[SkillRegistration],
        metrics: SkillMetrics,
        health: Optional[HealthScore],
        regime: str,
    ) -> SkillWeight:
        reasons: List[str] = [f"Regime: {regime}"]

        base = self._base_weight(registration)
        regime_mul = self._regime_multiplier(skill_name, regime)
        reasons.append(f"Regime multiplier: {regime_mul}")

        health_mul = self._health_multiplier(health)
        reasons.append(f"Health multiplier: {health_mul}")

        perf_mul = self._performance_multiplier(metrics)
        reasons.append(f"Performance multiplier: {perf_mul}")

        conf_mul = self._confidence_multiplier(opinion)
        reasons.append(f"Confidence multiplier: {conf_mul}")

        spec_mul = self._specialization_multiplier(skill_name, opinion)
        if spec_mul > 1.0:
            reasons.append(f"Specialization bonus: {spec_mul}")

        final = base * regime_mul * health_mul * perf_mul * conf_mul * spec_mul

        return SkillWeight(
            skill_name=skill_name,
            final_weight=round(final, 6),
            base_weight=round(base, 4),
            regime_multiplier=round(regime_mul, 4),
            health_multiplier=round(health_mul, 4),
            performance_multiplier=round(perf_mul, 4),
            confidence_multiplier=round(conf_mul, 4),
            specialization_multiplier=round(spec_mul, 4),
            normalization_factor=1.0,
            reasons=reasons,
        )

    @staticmethod
    def _infer_regime(world_model: Optional[WorldModel]) -> str:
        if world_model is None:
            return "uncertain"

        if world_model.regime_confidence < REGIME_CONFIDENCE_MIN:
            return "uncertain"

        regime = (world_model.regime or "").lower().strip()
        if regime in ("trending", "ranging", "volatile", "uncertain"):
            return regime

        state = world_model.state
        if state in (MarketState.STRONG_TREND_UP, MarketState.STRONG_TREND_DOWN,
                     MarketState.BULL, MarketState.BEAR,
                     MarketState.WEAK_TREND_UP, MarketState.WEAK_TREND_DOWN):
            return "trending"
        if state in (MarketState.RANGING, MarketState.ACCUMULATION,
                     MarketState.DISTRIBUTION, MarketState.COMPRESSION):
            return "ranging"
        if state == MarketState.HIGH_VOLATILITY:
            return "volatile"

        return "uncertain"

    @staticmethod
    def _base_weight(registration: Optional[SkillRegistration]) -> float:
        if registration is None:
            return BASE_WEIGHT_DEFAULT
        return max(0.1, registration.computational_cost)

    @staticmethod
    def _regime_multiplier(skill_name: str, regime: str) -> float:
        regime_config = REGIME_MULTIPLIERS.get(regime, REGIME_MULTIPLIERS["uncertain"])
        return regime_config.get(skill_name, regime_config.get("default", 0.7))

    @staticmethod
    def _health_multiplier(health: Optional[HealthScore]) -> float:
        if health is None:
            return 1.0
        score = health.score
        if score >= HEALTH_EXCELLENT:
            return HEALTH_MULTIPLIERS["excellent"]
        if score >= HEALTH_GOOD:
            return HEALTH_MULTIPLIERS["good"]
        if score >= HEALTH_FAIR:
            return HEALTH_MULTIPLIERS["fair"]
        if score >= HEALTH_DEGRADED:
            return HEALTH_MULTIPLIERS["degraded"]
        return HEALTH_MULTIPLIERS["critical"]

    @staticmethod
    def _performance_multiplier(metrics: SkillMetrics) -> float:
        prec = metrics.historical_precision
        if prec >= PERFORMANCE_THRESHOLD_HIGH:
            return PERFORMANCE_MULTIPLIERS["high"]
        if prec >= PERFORMANCE_THRESHOLD_LOW:
            return PERFORMANCE_MULTIPLIERS["medium"]
        return PERFORMANCE_MULTIPLIERS["low"]

    @staticmethod
    def _confidence_multiplier(opinion: SkillOpinion) -> float:
        conf = opinion.confidence
        if conf >= CONFIDENCE_THRESHOLD_HIGH:
            return CONFIDENCE_MULTIPLIERS["high"]
        if conf >= CONFIDENCE_THRESHOLD_LOW:
            return CONFIDENCE_MULTIPLIERS["medium"]
        return CONFIDENCE_MULTIPLIERS["low"]

    @staticmethod
    def _tokenize(text: str) -> Set[str]:
        text = text.lower()
        tokens = set(re.findall(r"\b[a-záéíóúãõç0-9]+\b", text))
        stop_words = {
            "o", "a", "os", "as", "um", "uma", "de", "da", "do",
            "em", "para", "com", "por", "que", "e", "nao", "se",
            "mais", "mas", "ao", "tem", "ha", "entre",
        }
        return tokens - stop_words

    @staticmethod
    def _specialization_multiplier(skill_name: str, opinion: SkillOpinion) -> float:
        keywords = SPECIALIZATION_KEYWORDS.get(skill_name.lower())
        if not keywords:
            return 1.0

        evidence_tokens: Set[str] = set()
        for ev in opinion.evidence:
            evidence_tokens |= DynamicWeightCalculator._tokenize(ev)
        evidence_tokens |= DynamicWeightCalculator._tokenize(opinion.observations)

        matched = evidence_tokens & keywords
        if len(matched) >= 2:
            return 1.5
        if len(matched) == 1:
            return 1.2
        return 1.0

    @staticmethod
    def _normalize(
        raw_weights: List[tuple],
    ) -> Dict[str, SkillWeight]:
        if not raw_weights:
            return {}

        total = sum(sw.final_weight for _, sw in raw_weights)
        if total <= 0.0:
            return _make_equal_distribution(
                raw_weights, "Equal distribution (total was zero)"
            )

        norm_factor = NORMALIZE_TARGET / total

        pre_clamp = {name: (sw, sw.final_weight * norm_factor) for name, sw in raw_weights}

        clamped_names = set()
        for name, (sw, nw) in pre_clamp.items():
            if nw > MAX_WEIGHT_PER_SKILL:
                clamped_names.add(name)

        n_skills = len(pre_clamp)
        if n_skills == 1:
            name, (sw, nw) = next(iter(pre_clamp.items()))
            return {name: _make_sw(sw, NORMALIZE_TARGET, NORMALIZE_TARGET / sw.final_weight,
                                   sw.reasons + ["Single skill — full weight"])}

        clamped_total = len(clamped_names) * MAX_WEIGHT_PER_SKILL
        remaining = NORMALIZE_TARGET - clamped_total

        if remaining < 0:
            return _make_equal_distribution(
                raw_weights, "All skills clamped — equal distribution"
            )

        unclamped = {n: (sw, nw) for n, (sw, nw) in pre_clamp.items()
                     if n not in clamped_names}
        unclamped_raw = sum(nw for _, nw in unclamped.values())

        if not unclamped or unclamped_raw <= 0:
            return _make_equal_distribution(
                raw_weights, "No unclamped skills — equal distribution"
            )

        result = {}
        for name, (sw, nw) in pre_clamp.items():
            if name in clamped_names:
                nf = MAX_WEIGHT_PER_SKILL / sw.final_weight if sw.final_weight > 0 else 1.0
                result[name] = _make_sw(
                    sw, MAX_WEIGHT_PER_SKILL, nf,
                    sw.reasons + [f"Clamped at max ({MAX_WEIGHT_PER_SKILL})"],
                )
            else:
                fair = nw / unclamped_raw * remaining
                nf = fair / sw.final_weight if sw.final_weight > 0 else 1.0
                result[name] = _make_sw(
                    sw, fair, nf,
                    sw.reasons + [f"Normalized + redistributed (factor: {nf:.4f})"],
                )

        return result

    @staticmethod
    def _compute_hash(weights: Dict[str, SkillWeight]) -> str:
        parts = [f"{name}|{w.final_weight}" for name, w in sorted(weights.items())]
        return hashlib.sha256("||".join(parts).encode("utf-8")).hexdigest()

    @staticmethod
    def _empty() -> WeightDistribution:
        return WeightDistribution(
            weights={},
            total_weight=0.0,
            normalized=False,
            distribution_hash=hashlib.sha256(b"empty").hexdigest(),
        )
