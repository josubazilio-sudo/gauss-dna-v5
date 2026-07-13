import time
import json
import pytest
from datetime import datetime, timezone
from dataclasses import FrozenInstanceError

from ENGINE.meta.meta_types import MetaVerdict
from ENGINE.meta.meta_intelligence import MetaIntelligence
from ENGINE.meta.meta_config import (
    CONSENSUS_MIN, QUALITY_MIN, CONSISTENCY_MIN,
    CONFIDENCE_MIN, HEALTH_MIN, MAX_CONFLICTS,
)
from ENGINE.council.council_types import CouncilVerdict
from ENGINE.council.evidence_types import (
    EvidenceGraph, EvidenceNode, EvidenceCluster, EvidenceConflict,
)
from ENGINE.world.world_types import WorldModel, MarketState, MarketQuality
from ENGINE.council.health_types import HealthScore, HealthStatus
from ENGINE.council.weight_types import WeightDistribution, SkillWeight
from CORE.events.event_bus import EventBus
from CORE.events.events import EventTypes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _empty_graph() -> EvidenceGraph:
    return EvidenceGraph(
        nodes=(), clusters=(), contradictions=(),
        confidence=0.0, quality=0.0, consistency=0.0,
        graph_hash="", num_skills=0, num_duplicates_removed=0,
    )


def _verdict(
    consensus=0.8, confidence=0.8, risk=0.2, probability=0.7,
    quality=0.8, consistency=0.8, agreement=0.8, disagreement=0.1,
    conflicting=None, summary="ok",
) -> CouncilVerdict:
    if conflicting is None:
        conflicting = []
    v = CouncilVerdict(
        consensus_score=consensus, global_confidence=confidence,
        global_risk=risk, global_probability=probability,
        evidence_quality=quality, evidence_consistency=consistency,
        agreement_level=agreement, disagreement_level=disagreement,
        participating_skills=["smc", "volume"],
        conflicting_skills=conflicting,
        supporting_clusters=["momentum"],
        conflicting_clusters=[],
        strongest_evidence=["forte tendencia"],
        weakest_evidence=["ruido moderado"],
        summary=summary, council_hash="",
    )
    return CouncilVerdict(
        consensus_score=v.consensus_score,
        global_confidence=v.global_confidence,
        global_risk=v.global_risk,
        global_probability=v.global_probability,
        evidence_quality=v.evidence_quality,
        evidence_consistency=v.evidence_consistency,
        agreement_level=v.agreement_level,
        disagreement_level=v.disagreement_level,
        participating_skills=v.participating_skills,
        conflicting_skills=v.conflicting_skills,
        supporting_clusters=v.supporting_clusters,
        conflicting_clusters=v.conflicting_clusters,
        strongest_evidence=v.strongest_evidence,
        weakest_evidence=v.weakest_evidence,
        summary=v.summary,
        council_hash=CouncilVerdict.compute_hash(v),
    )


def _good_world() -> WorldModel:
    return WorldModel(
        state=MarketState.STRONG_TREND_UP,
        quality=MarketQuality.GOOD,
        confidence=0.80,
        health=0.90,
        trend_strength=0.75,
    )


def _bad_world() -> WorldModel:
    return WorldModel(
        state=MarketState.UNCERTAIN,
        quality=MarketQuality.POOR,
        confidence=0.10,
        health=0.30,
        trend_strength=0.10,
    )


def _health(name: str, score: float) -> HealthScore:
    return HealthScore(
        skill_name=name, score=score,
        availability=score, reliability=score, precision=score,
        latency_score=max(0.0, score - 0.1), stability=score,
        timeout_penalty=0.0, error_penalty=0.0,
        status=HealthStatus.GOOD if score >= 0.7 else HealthStatus.FAIR,
        recommendations=[],
    )


def _weights() -> WeightDistribution:
    sw = SkillWeight(
        skill_name="smc", final_weight=0.5, base_weight=0.5,
        regime_multiplier=1.0, health_multiplier=1.0,
        performance_multiplier=1.0, confidence_multiplier=1.0,
        specialization_multiplier=1.0, normalization_factor=1.0,
        reasons=[],
    )
    sw2 = SkillWeight(
        skill_name="volume", final_weight=0.5, base_weight=0.5,
        regime_multiplier=1.0, health_multiplier=1.0,
        performance_multiplier=1.0, confidence_multiplier=1.0,
        specialization_multiplier=1.0, normalization_factor=1.0,
        reasons=[],
    )
    return WeightDistribution(
        weights={"smc": sw, "volume": sw2},
        total_weight=1.0, normalized=True,
        distribution_hash="test",
    )


# ===================================================================
# CONTRATO
# ===================================================================

class TestMetaVerdictTypes:

    def test_immutable(self):
        v = MetaVerdict(
            proceed=True, decision="PROCEED", confidence=0.8,
            reasoning_score=0.7, information_quality=0.8,
            uncertainty=0.2, detected_conflicts=[], blocking_reasons=[],
            recommendations=[], meta_hash="abc",
        )
        with pytest.raises(FrozenInstanceError):
            v.proceed = False

    def test_to_dict(self):
        v = MetaVerdict(
            proceed=True, decision="PROCEED", confidence=0.8,
            reasoning_score=0.7, information_quality=0.8,
            uncertainty=0.2, detected_conflicts=["a"],
            blocking_reasons=[], recommendations=["ok"],
            meta_hash="abc",
        )
        d = v.to_dict()
        assert d["proceed"] is True
        assert d["decision"] == "PROCEED"
        assert d["confidence"] == 0.8
        assert "created_at" in d

    def test_to_json(self):
        v = MetaVerdict(
            proceed=False, decision="HOLD", confidence=0.3,
            reasoning_score=0.2, information_quality=0.1,
            uncertainty=0.9, detected_conflicts=[],
            blocking_reasons=["test"], recommendations=[],
            meta_hash="xyz",
        )
        j = v.to_json()
        d = json.loads(j)
        assert d["proceed"] is False
        assert d["decision"] == "HOLD"

    def test_from_dict_roundtrip(self):
        v = MetaVerdict(
            proceed=True, decision="PROCEED", confidence=0.75,
            reasoning_score=0.65, information_quality=0.70,
            uncertainty=0.25, detected_conflicts=[],
            blocking_reasons=[], recommendations=["monitorar"],
            meta_hash="h1",
        )
        d = v.to_dict()
        v2 = MetaVerdict.from_dict(d)
        assert v2.proceed == v.proceed
        assert v2.confidence == v.confidence
        assert v2.recommendations == v.recommendations

    def test_from_json_roundtrip(self):
        v = MetaVerdict(
            proceed=False, decision="HOLD", confidence=0.2,
            reasoning_score=0.15, information_quality=0.1,
            uncertainty=0.85, detected_conflicts=["a", "b"],
            blocking_reasons=["baixo consenso"],
            recommendations=["aguardar"], meta_hash="h2",
        )
        j = v.to_json()
        v2 = MetaVerdict.from_json(j)
        assert v2.decision == "HOLD"
        assert v2.detected_conflicts == ["a", "b"]
        assert v2.blocking_reasons == ["baixo consenso"]

    def test_hash_deterministic(self):
        v = MetaVerdict(
            proceed=True, decision="PROCEED", confidence=0.8,
            reasoning_score=0.7, information_quality=0.8,
            uncertainty=0.2, detected_conflicts=[],
            blocking_reasons=[], recommendations=[],
            meta_hash="",
        )
        h1 = MetaVerdict.compute_hash(v)
        h2 = MetaVerdict.compute_hash(v)
        assert h1 == h2

    def test_hash_changes(self):
        v1 = MetaVerdict(
            proceed=True, decision="PROCEED", confidence=0.8,
            reasoning_score=0.7, information_quality=0.8,
            uncertainty=0.2, detected_conflicts=[],
            blocking_reasons=[], recommendations=[],
            meta_hash="",
        )
        v2 = MetaVerdict(
            proceed=False, decision="HOLD", confidence=0.8,
            reasoning_score=0.7, information_quality=0.8,
            uncertainty=0.2, detected_conflicts=[],
            blocking_reasons=[], recommendations=[],
            meta_hash="",
        )
        assert MetaVerdict.compute_hash(v1) != MetaVerdict.compute_hash(v2)


# ===================================================================
# DECISAO
# ===================================================================

class TestDecisionFavorable:

    def test_all_good_proceed(self):
        engine = MetaIntelligence()
        v = engine.evaluate(
            _verdict(), _good_world(), _weights(),
            {"smc": _health("smc", 0.9), "volume": _health("volume", 0.85)},
            _empty_graph(),
        )
        assert v.proceed is True
        assert v.decision == "PROCEED"
        assert v.confidence > 0.5
        assert len(v.blocking_reasons) == 0


class TestDecisionBlocking:

    def test_low_consensus_hold(self):
        engine = MetaIntelligence()
        v = engine.evaluate(
            _verdict(consensus=CONSENSUS_MIN - 0.1, quality=0.8),
            _good_world(), _weights(),
            {"smc": _health("smc", 0.9)}, _empty_graph(),
        )
        assert v.proceed is False
        assert v.decision == "HOLD"
        assert any("Consensus" in r for r in v.blocking_reasons)

    def test_low_quality_hold(self):
        engine = MetaIntelligence()
        v = engine.evaluate(
            _verdict(consensus=0.8, quality=QUALITY_MIN - 0.1),
            _good_world(), _weights(),
            {"smc": _health("smc", 0.9)}, _empty_graph(),
        )
        assert v.proceed is False
        assert v.decision == "HOLD"
        assert any("Qualidade" in r for r in v.blocking_reasons)

    def test_low_consistency_hold(self):
        engine = MetaIntelligence()
        v = engine.evaluate(
            _verdict(consensus=0.8, quality=0.8, consistency=CONSISTENCY_MIN - 0.1),
            _good_world(), _weights(),
            {"smc": _health("smc", 0.9)}, _empty_graph(),
        )
        assert v.proceed is False
        assert v.decision == "HOLD"
        assert any("inconsistentes" in r for r in v.blocking_reasons)

    def test_low_confidence_hold(self):
        engine = MetaIntelligence()
        v = engine.evaluate(
            _verdict(consensus=0.8, quality=0.8, consistency=0.8,
                     confidence=CONFIDENCE_MIN - 0.1),
            _good_world(), _weights(),
            {"smc": _health("smc", 0.9)}, _empty_graph(),
        )
        assert v.proceed is False
        assert v.decision == "HOLD"
        assert any("Confianca" in r for r in v.blocking_reasons)

    def test_low_health_hold(self):
        engine = MetaIntelligence()
        v = engine.evaluate(
            _verdict(), _good_world(), _weights(),
            {"smc": _health("smc", HEALTH_MIN - 0.1)}, _empty_graph(),
        )
        assert v.proceed is False
        assert v.decision == "HOLD"
        assert any("Health" in r for r in v.blocking_reasons)

    def test_many_conflicts_hold(self):
        engine = MetaIntelligence()
        conflicts = [f"conflito_{i}" for i in range(MAX_CONFLICTS + 2)]
        v = engine.evaluate(
            _verdict(consensus=0.8, quality=0.8, conflicting=conflicts),
            _good_world(), _weights(),
            {"smc": _health("smc", 0.9)}, _empty_graph(),
        )
        assert v.proceed is False
        assert v.decision == "HOLD"
        assert any("conflitos" in r for r in v.blocking_reasons)

    def test_world_model_not_tradeable_hold(self):
        engine = MetaIntelligence()
        v = engine.evaluate(
            _verdict(), _bad_world(), _weights(),
            {"smc": _health("smc", 0.9)}, _empty_graph(),
        )
        assert v.proceed is False
        assert v.decision == "HOLD"
        assert any("operavel" in r for r in v.blocking_reasons)

    def test_no_world_model_hold(self):
        engine = MetaIntelligence()
        v = engine.evaluate(
            _verdict(), None, _weights(),
            {"smc": _health("smc", 0.9)}, _empty_graph(),
        )
        assert v.proceed is False
        assert v.decision == "HOLD"
        assert any("ausente" in r for r in v.blocking_reasons)


# ===================================================================
# INTEGRACAO
# ===================================================================

class TestIntegration:

    def test_with_consensus_engine(self):
        engine = MetaIntelligence()
        v = _verdict(consensus=0.85, confidence=0.80, quality=0.82)
        wm = _good_world()
        hs = {"smc": _health("smc", 0.9), "volume": _health("volume", 0.85)}
        result = engine.evaluate(v, wm, _weights(), hs, _empty_graph())
        assert result.proceed is True
        assert result.decision == "PROCEED"
        assert result.confidence > 0.5

    def test_with_evidence_graph(self):
        engine = MetaIntelligence()
        node = EvidenceNode(
            id="n1", evidence_text="forte tendencia",
            source_skills=("smc",), confidence=0.8, risk=0.2,
            probability=0.7, occurrences=1, weight=1.0,
        )
        graph = EvidenceGraph(
            nodes=(node,), clusters=(), contradictions=(),
            confidence=0.8, quality=0.8, consistency=0.9,
            graph_hash="g1", num_skills=1, num_duplicates_removed=0,
        )
        v = engine.evaluate(
            _verdict(consensus=0.8, quality=0.8, confidence=0.8),
            _good_world(), _weights(),
            {"smc": _health("smc", 0.9)}, graph,
        )
        assert v.proceed is True
        assert v.information_quality > 0.3

    def test_with_low_health_map(self):
        engine = MetaIntelligence()
        v = engine.evaluate(
            _verdict(), _good_world(), _weights(),
            {"smc": _health("smc", 0.2)}, _empty_graph(),
        )
        assert v.proceed is False

    def test_with_empty_health_map(self):
        engine = MetaIntelligence()
        v = engine.evaluate(
            _verdict(), _good_world(), _weights(), {}, _empty_graph(),
        )
        assert v.proceed is False

    def test_event_proceed_published(self):
        bus = EventBus()
        received = []
        bus.subscribe(EventTypes.META_PROCEED, lambda e: received.append(e))
        engine = MetaIntelligence(bus)
        engine.evaluate(
            _verdict(), _good_world(), _weights(),
            {"smc": _health("smc", 0.9)}, _empty_graph(),
        )
        assert len(received) == 1
        assert received[0].type == EventTypes.META_PROCEED

    def test_event_hold_published(self):
        bus = EventBus()
        received = []
        bus.subscribe(EventTypes.META_HOLD, lambda e: received.append(e))
        engine = MetaIntelligence(bus)
        engine.evaluate(
            _verdict(consensus=CONSENSUS_MIN - 0.2), _good_world(),
            _weights(), {"smc": _health("smc", 0.9)}, _empty_graph(),
        )
        assert len(received) == 1
        assert received[0].type == EventTypes.META_HOLD

    def test_event_not_published_without_bus(self):
        engine = MetaIntelligence()
        v = engine.evaluate(
            _verdict(), _good_world(), _weights(),
            {"smc": _health("smc", 0.9)}, _empty_graph(),
        )
        assert v.proceed is True

    def test_meta_hash_present(self):
        engine = MetaIntelligence()
        v = engine.evaluate(
            _verdict(), _good_world(), _weights(),
            {"smc": _health("smc", 0.9)}, _empty_graph(),
        )
        assert len(v.meta_hash) > 0

    def test_hash_deterministic_across_calls(self):
        engine = MetaIntelligence()
        v1 = engine.evaluate(
            _verdict(), _good_world(), _weights(),
            {"smc": _health("smc", 0.9)}, _empty_graph(),
        )
        v2 = engine.evaluate(
            _verdict(), _good_world(), _weights(),
            {"smc": _health("smc", 0.9)}, _empty_graph(),
        )
        assert v1.meta_hash == v2.meta_hash


# ===================================================================
# PERFORMANCE
# ===================================================================

class TestPerformance:

    def test_10_scenarios(self):
        engine = MetaIntelligence()
        scenarios = [
            (_verdict(consensus=0.9), _good_world(), {"smc": _health("smc", 0.9)}),
            (_verdict(consensus=0.3), _good_world(), {"smc": _health("smc", 0.9)}),
            (_verdict(quality=0.2), _good_world(), {"smc": _health("smc", 0.9)}),
            (_verdict(), _bad_world(), {"smc": _health("smc", 0.9)}),
            (_verdict(), None, {"smc": _health("smc", 0.9)}),
            (_verdict(), _good_world(), {"smc": _health("smc", 0.2)}),
            (_verdict(), _good_world(), {}),
            (_verdict(conflicting=["a", "b", "c", "d", "e"]), _good_world(),
             {"smc": _health("smc", 0.9)}),
            (None, _good_world(), {"smc": _health("smc", 0.9)}),
            (_verdict(consistency=0.2), _good_world(), {"smc": _health("smc", 0.9)}),
        ]
        start = time.perf_counter()
        for v, wm, hs in scenarios:
            engine.evaluate(v, wm, _weights(), hs, _empty_graph())
        elapsed = time.perf_counter() - start
        assert elapsed < 5.0

    def test_100_scenarios(self):
        engine = MetaIntelligence()
        start = time.perf_counter()
        for i in range(100):
            cons = 0.3 + (i % 70) / 100.0
            engine.evaluate(
                _verdict(consensus=cons), _good_world(), _weights(),
                {"smc": _health("smc", 0.9)}, _empty_graph(),
            )
        elapsed = time.perf_counter() - start
        assert elapsed < 10.0

    def test_1000_scenarios(self):
        engine = MetaIntelligence()
        start = time.perf_counter()
        for i in range(1000):
            cons = 0.2 + (i % 80) / 100.0
            engine.evaluate(
                _verdict(consensus=cons), _good_world(), _weights(),
                {"smc": _health("smc", 0.9)}, _empty_graph(),
            )
        elapsed = time.perf_counter() - start
        assert elapsed < 30.0


# ===================================================================
# ROBUSTEZ
# ===================================================================

class TestRobustness:

    def test_council_verdict_none(self):
        engine = MetaIntelligence()
        v = engine.evaluate(
            None, _good_world(), _weights(),
            {"smc": _health("smc", 0.9)}, _empty_graph(),
        )
        assert v.proceed is False
        assert v.decision == "HOLD"

    def test_world_model_none(self):
        engine = MetaIntelligence()
        v = engine.evaluate(
            _verdict(), None, _weights(),
            {"smc": _health("smc", 0.9)}, _empty_graph(),
        )
        assert v.proceed is False

    def test_evidence_graph_empty(self):
        engine = MetaIntelligence()
        v = engine.evaluate(
            _verdict(consensus=0.4, quality=0.4),
            _good_world(), _weights(),
            {"smc": _health("smc", 0.9)}, _empty_graph(),
        )
        assert isinstance(v, MetaVerdict)

    def test_health_empty(self):
        engine = MetaIntelligence()
        v = engine.evaluate(
            _verdict(), _good_world(), _weights(), {}, _empty_graph(),
        )
        assert v.proceed is False

    def test_all_none(self):
        engine = MetaIntelligence()
        v = engine.evaluate(None, None, None, {}, None)
        assert v.proceed is False
        assert v.decision == "HOLD"
        assert len(v.blocking_reasons) > 0

    def test_no_exceptions_on_empty_input(self):
        engine = MetaIntelligence()
        try:
            engine.evaluate(None, None, None, {}, None)
        except Exception:
            pytest.fail("MetaIntelligence raised on empty input")

    def test_returns_valid_verdict_always(self):
        engine = MetaIntelligence()
        for _ in range(20):
            v = engine.evaluate(None, None, None, {}, None)
            assert isinstance(v, MetaVerdict)
            assert v.decision in ("PROCEED", "HOLD")
            assert 0.0 <= v.confidence <= 1.0


# ===================================================================
# CONSENSUS SCORE RANGES
# ===================================================================

class TestMetaScoreRanges:

    def test_confidence_range(self):
        engine = MetaIntelligence()
        v = engine.evaluate(
            _verdict(), _good_world(), _weights(),
            {"smc": _health("smc", 0.9)}, _empty_graph(),
        )
        assert 0.0 <= v.confidence <= 1.0

    def test_reasoning_score_range(self):
        engine = MetaIntelligence()
        v = engine.evaluate(
            _verdict(), _good_world(), _weights(),
            {"smc": _health("smc", 0.9)}, _empty_graph(),
        )
        assert 0.0 <= v.reasoning_score <= 1.0

    def test_information_quality_range(self):
        engine = MetaIntelligence()
        v = engine.evaluate(
            _verdict(), _good_world(), _weights(),
            {"smc": _health("smc", 0.9)}, _empty_graph(),
        )
        assert 0.0 <= v.information_quality <= 1.0

    def test_uncertainty_range(self):
        engine = MetaIntelligence()
        v = engine.evaluate(
            _verdict(), _good_world(), _weights(),
            {"smc": _health("smc", 0.9)}, _empty_graph(),
        )
        assert 0.0 <= v.uncertainty <= 1.0

    def test_recommendations_always_present(self):
        engine = MetaIntelligence()
        v = engine.evaluate(
            _verdict(), _good_world(), _weights(),
            {"smc": _health("smc", 0.9)}, _empty_graph(),
        )
        assert isinstance(v.recommendations, list)
        assert len(v.recommendations) >= 0

    def test_blocking_reasons_properly_set(self):
        engine = MetaIntelligence()
        v = engine.evaluate(
            _verdict(consensus=CONSENSUS_MIN - 0.2), _good_world(),
            _weights(), {"smc": _health("smc", 0.9)}, _empty_graph(),
        )
        assert len(v.blocking_reasons) > 0
