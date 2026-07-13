import sys
import json
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import unittest

from ENGINE.world.world_types import WorldModel, MarketState, MarketQuality
from ENGINE.skills.skill_opinion import SkillOpinion, SkillMetrics
from ENGINE.skills.skill_registry import SkillRegistration
from ENGINE.skills.base import BaseSkill
from ENGINE.council.health_types import HealthScore, HealthStatus
from ENGINE.council.weight_types import SkillWeight, WeightDistribution
from ENGINE.council.weight_config import (
    MAX_WEIGHT_PER_SKILL,
    REGIME_MULTIPLIERS,
)
from ENGINE.council.dynamic_weights import DynamicWeightCalculator


def _opinion(name: str, conf: float = 0.7, risk: float = 0.3,
             prob: float = 0.6, evidence: Optional[List[str]] = None,
             obs: str = "") -> SkillOpinion:
    return SkillOpinion(
        skill_name=name, confidence=conf, risk=risk,
        probability=prob, evidence=evidence or ["evidencia generica"],
        observations=obs, success=True,
    )


def _metrics(precision: float = 0.0) -> SkillMetrics:
    return SkillMetrics(
        availability=1.0, avg_latency_ms=50,
        historical_precision=precision, reliability=1.0,
        total_calls=100, successful_calls=90,
    )


def _health(score: float) -> HealthScore:
    if score >= 0.9:
        st = HealthStatus.EXCELLENT
    elif score >= 0.7:
        st = HealthStatus.GOOD
    elif score >= 0.5:
        st = HealthStatus.FAIR
    elif score >= 0.3:
        st = HealthStatus.DEGRADED
    else:
        st = HealthStatus.CRITICAL
    return HealthScore(
        skill_name="x", score=score, availability=min(1.0, score),
        reliability=min(1.0, score), precision=min(1.0, score),
        latency_score=1.0, stability=1.0, timeout_penalty=0.0,
        error_penalty=0.0, status=st, recommendations=[],
    )


def _reg(name: str, cost: float = 0.5) -> SkillRegistration:
    return SkillRegistration(
        name=name, category="analysis", version="1.0",
        computational_cost=cost,
    )


def _world(regime: str = "trending", state: MarketState = MarketState.BULL,
           conf: float = 0.8) -> WorldModel:
    return WorldModel(
        state=state, quality=MarketQuality.GOOD,
        regime=regime, regime_confidence=conf,
    )


class TestWeightTypes(unittest.TestCase):

    def test_skill_weight_immutable(self):
        sw = SkillWeight(
            skill_name="smc", final_weight=0.5, base_weight=0.5,
            regime_multiplier=1.0, health_multiplier=1.0,
            performance_multiplier=1.0, confidence_multiplier=1.0,
            specialization_multiplier=1.0, normalization_factor=1.0,
            reasons=[],
        )
        with self.assertRaises(AttributeError):
            sw.final_weight = 0.3

    def test_weight_distribution_immutable(self):
        wd = WeightDistribution(
            weights={}, total_weight=0.0, normalized=False,
            distribution_hash="abc",
        )
        with self.assertRaises(AttributeError):
            wd.normalized = True

    def test_skill_weight_to_dict(self):
        sw = SkillWeight(
            skill_name="smc", final_weight=0.6, base_weight=0.5,
            regime_multiplier=1.2, health_multiplier=1.0,
            performance_multiplier=1.0, confidence_multiplier=1.0,
            specialization_multiplier=1.0, normalization_factor=1.0,
            reasons=["teste"],
        )
        d = sw.to_dict()
        self.assertEqual(d["skill_name"], "smc")
        self.assertEqual(d["final_weight"], 0.6)
        self.assertIn("reasons", d)

    def test_weight_distribution_to_json_roundtrip(self):
        sw = SkillWeight(
            skill_name="smc", final_weight=0.5, base_weight=0.5,
            regime_multiplier=1.0, health_multiplier=1.0,
            performance_multiplier=1.0, confidence_multiplier=1.0,
            specialization_multiplier=1.0, normalization_factor=1.0,
            reasons=[],
        )
        original = WeightDistribution(
            weights={"smc": sw}, total_weight=0.5, normalized=True,
            distribution_hash="hash123",
        )
        j = original.to_json()
        restored = WeightDistribution.from_json(j)
        self.assertEqual(restored.total_weight, 0.5)
        self.assertEqual(restored.normalized, True)
        self.assertIn("smc", restored.weights)
        self.assertEqual(restored.weights["smc"].final_weight, 0.5)

    def test_hash_deterministic(self):
        calc = DynamicWeightCalculator()
        ops = [_opinion("smc"), _opinion("volume")]
        regs = {"smc": _reg("smc"), "volume": _reg("volume")}
        mets = {"smc": _metrics(0.8), "volume": _metrics(0.8)}
        hlth = {"smc": _health(0.9), "volume": _health(0.9)}
        wm = _world("trending")

        d1 = calc.calculate_all(ops, regs, mets, hlth, wm)
        d2 = calc.calculate_all(ops, regs, mets, hlth, wm)
        self.assertEqual(d1.distribution_hash, d2.distribution_hash)

    def test_hash_changes_with_different_input(self):
        calc = DynamicWeightCalculator()
        ops1 = [_opinion("smc", conf=0.7), _opinion("volume", conf=0.6),
                _opinion("macro", conf=0.5)]
        ops2 = [_opinion("smc", conf=0.3), _opinion("volume", conf=0.4),
                _opinion("macro", conf=0.9)]
        regs = {o.skill_name: _reg(o.skill_name) for o in ops1}
        mets = {o.skill_name: _metrics(0.8) for o in ops1}
        hlth = {o.skill_name: _health(0.9) for o in ops1}
        wm = _world("trending")

        d1 = calc.calculate_all(ops1, regs, mets, hlth, wm)
        d2 = calc.calculate_all(ops2, regs, mets, hlth, wm)
        self.assertNotEqual(d1.distribution_hash, d2.distribution_hash)

    def test_from_dict_weight_distribution(self):
        sw = SkillWeight(
            skill_name="test", final_weight=1.0, base_weight=0.5,
            regime_multiplier=1.0, health_multiplier=1.0,
            performance_multiplier=1.0, confidence_multiplier=1.0,
            specialization_multiplier=1.0, normalization_factor=1.0,
            reasons=[],
        )
        original = WeightDistribution(
            weights={"test": sw}, total_weight=1.0, normalized=True,
            distribution_hash="h",
        )
        d = original.to_dict()
        restored = WeightDistribution.from_dict(d)
        self.assertEqual(restored.weights["test"].final_weight, 1.0)


class TestDynamicWeightCalculation(unittest.TestCase):

    def setUp(self):
        self.calc = DynamicWeightCalculator()

    def _default_run(self, opinions, regs=None, mets=None, hlth=None, wm=None):
        names = {o.skill_name for o in opinions}
        regs = regs or {n: _reg(n) for n in names}
        mets = mets or {n: _metrics(0.8) for n in names}
        hlth = hlth or {n: _health(0.9) for n in names}
        wm = wm or _world("trending")
        return self.calc.calculate_all(opinions, regs, mets, hlth, wm)

    def test_base_weight_from_registration(self):
        ops = [_opinion("smc")]
        regs = {"smc": _reg("smc", cost=0.3)}
        mets = {"smc": _metrics(0.8)}
        hlth = {"smc": _health(0.9)}
        wm = _world("trending")
        dist = self.calc.calculate_all(ops, regs, mets, hlth, wm)
        self.assertEqual(dist.weights["smc"].base_weight, 0.3)

    def test_health_high_score(self):
        ops = [_opinion("smc")]
        hlth = {"smc": _health(0.95)}
        dist = self._default_run(ops, hlth=hlth)
        self.assertGreater(dist.weights["smc"].health_multiplier, 1.0)

    def test_health_low_score(self):
        ops = [_opinion("smc")]
        hlth = {"smc": _health(0.1)}
        dist = self._default_run(ops, hlth=hlth)
        self.assertLess(dist.weights["smc"].health_multiplier, 0.5)

    def test_regime_trending(self):
        ops = [_opinion("smc")]
        wm = _world("trending", MarketState.BULL)
        dist = self._default_run(ops, wm=wm)
        self.assertGreater(dist.weights["smc"].regime_multiplier, 1.0)

    def test_regime_ranging(self):
        ops = [_opinion("liquidity")]
        wm = _world("ranging", MarketState.RANGING)
        dist = self._default_run(ops, wm=wm)
        self.assertGreater(dist.weights["liquidity"].regime_multiplier, 1.0)

    def test_regime_volatile(self):
        ops = [_opinion("risk")]
        wm = _world("volatile", MarketState.HIGH_VOLATILITY)
        dist = self._default_run(ops, wm=wm)
        self.assertGreater(dist.weights["risk"].regime_multiplier, 1.0)

    def test_regime_uncertain_reduces_all(self):
        ops = [_opinion("smc")]
        wm = _world("uncertain", MarketState.UNCERTAIN, conf=0.1)
        dist = self._default_run(ops, wm=wm)
        self.assertLess(dist.weights["smc"].regime_multiplier, 1.0)

    def test_high_performance(self):
        ops = [_opinion("smc")]
        mets = {"smc": _metrics(0.9)}
        dist = self._default_run(ops, mets=mets)
        self.assertGreater(dist.weights["smc"].performance_multiplier, 1.0)

    def test_low_performance(self):
        ops = [_opinion("smc")]
        mets = {"smc": _metrics(0.1)}
        dist = self._default_run(ops, mets=mets)
        self.assertLess(dist.weights["smc"].performance_multiplier, 1.0)

    def test_high_confidence(self):
        ops = [_opinion("smc", conf=0.9)]
        dist = self._default_run(ops)
        self.assertGreater(dist.weights["smc"].confidence_multiplier, 1.0)

    def test_low_confidence(self):
        ops = [_opinion("smc", conf=0.2)]
        dist = self._default_run(ops)
        self.assertLess(dist.weights["smc"].confidence_multiplier, 1.0)


class TestNormalization(unittest.TestCase):

    def setUp(self):
        self.calc = DynamicWeightCalculator()

    def test_sum_equals_one(self):
        ops = [_opinion("smc"), _opinion("volume"), _opinion("trend")]
        regs = {o.skill_name: _reg(o.skill_name) for o in ops}
        mets = {o.skill_name: _metrics(0.8) for o in ops}
        hlth = {o.skill_name: _health(0.9) for o in ops}
        wm = _world("trending")
        dist = self.calc.calculate_all(ops, regs, mets, hlth, wm)
        total = sum(sw.final_weight for sw in dist.weights.values())
        self.assertAlmostEqual(total, 1.0, places=4)

    def test_no_negative_weights(self):
        ops = [_opinion("smc")]
        dist = self.calc.calculate_all(ops, {"smc": _reg("smc")},
                                       {"smc": _metrics(0.0)},
                                       {"smc": _health(0.0)},
                                       _world("uncertain"))
        for sw in dist.weights.values():
            self.assertGreaterEqual(sw.final_weight, 0.0)

    def test_no_weight_above_max(self):
        ops = [_opinion("smc"), _opinion("volume")]
        regs = {"smc": _reg("smc", cost=1.0), "volume": _reg("volume", cost=0.1)}
        mets = {"smc": _metrics(0.95), "volume": _metrics(0.1)}
        hlth = {"smc": _health(1.0), "volume": _health(0.1)}
        wm = _world("trending")
        dist = self.calc.calculate_all(ops, regs, mets, hlth, wm)
        for sw in dist.weights.values():
            self.assertLessEqual(sw.final_weight, MAX_WEIGHT_PER_SKILL + 0.001)

    def test_two_skills_equal_weights(self):
        ops = [_opinion("a"), _opinion("b")]
        regs = {"a": _reg("a", 0.5), "b": _reg("b", 0.5)}
        mets = {"a": _metrics(0.5), "b": _metrics(0.5)}
        hlth = {"a": _health(0.5), "b": _health(0.5)}
        wm = _world("uncertain")
        dist = self.calc.calculate_all(ops, regs, mets, hlth, wm)
        w1 = dist.weights["a"].final_weight
        w2 = dist.weights["b"].final_weight
        self.assertAlmostEqual(w1, w2, places=4)

    def test_normalization_factor_recorded(self):
        ops = [_opinion("smc")]
        dist = self.calc.calculate_all(ops, {"smc": _reg("smc")},
                                       {"smc": _metrics(0.8)},
                                       {"smc": _health(0.9)},
                                       _world("trending"))
        self.assertGreater(dist.weights["smc"].normalization_factor, 0.0)


class TestSpecialization(unittest.TestCase):

    def setUp(self):
        self.calc = DynamicWeightCalculator()

    def test_smc_specialization(self):
        op = _opinion("smc", evidence=["BOS rompimento estrutura alta"])
        dist = self.calc.calculate_all(
            [op], {"smc": _reg("smc")},
            {"smc": _metrics(0.8)}, {"smc": _health(0.9)},
            _world("trending"),
        )
        self.assertGreater(dist.weights["smc"].specialization_multiplier, 1.0)

    def test_volume_specialization(self):
        op = _opinion("volume", evidence=["RVOL elevado fluxo institucional"])
        dist = self.calc.calculate_all(
            [op], {"volume": _reg("volume")},
            {"volume": _metrics(0.8)}, {"volume": _health(0.9)},
            _world("trending"),
        )
        self.assertGreater(dist.weights["volume"].specialization_multiplier, 1.0)

    def test_no_specialization_for_generic(self):
        op = _opinion("unknown", evidence=["generico sem keywords"])
        dist = self.calc.calculate_all(
            [op], {"unknown": _reg("unknown")},
            {"unknown": _metrics(0.8)}, {"unknown": _health(0.9)},
            _world("trending"),
        )
        self.assertEqual(dist.weights["unknown"].specialization_multiplier, 1.0)

    def test_no_specialization_with_wrong_keywords(self):
        op = _opinion("smc", evidence=["RVOL elevado fluxo"])
        dist = self.calc.calculate_all(
            [op], {"smc": _reg("smc")},
            {"smc": _metrics(0.8)}, {"smc": _health(0.9)},
            _world("trending"),
        )
        self.assertEqual(dist.weights["smc"].specialization_multiplier, 1.0)

    def test_partial_specialization_one_keyword(self):
        op = _opinion("smc", evidence=["apenas estrutura"])
        dist = self.calc.calculate_all(
            [op], {"smc": _reg("smc")},
            {"smc": _metrics(0.8)}, {"smc": _health(0.9)},
            _world("trending"),
        )
        self.assertEqual(dist.weights["smc"].specialization_multiplier, 1.2)


class TestRegimeInference(unittest.TestCase):

    def setUp(self):
        self.calc = DynamicWeightCalculator()

    def test_no_world_model_uncertain(self):
        regime = self.calc._infer_regime(None)
        self.assertEqual(regime, "uncertain")

    def test_regime_from_world_model_field(self):
        wm = _world("trending")
        self.assertEqual(self.calc._infer_regime(wm), "trending")

    def test_regime_from_state_when_field_unknown(self):
        wm = WorldModel(state=MarketState.STRONG_TREND_UP, regime="unknown",
                        regime_confidence=0.8)
        self.assertEqual(self.calc._infer_regime(wm), "trending")

    def test_regime_from_state_ranging(self):
        wm = WorldModel(state=MarketState.RANGING, regime="",
                        regime_confidence=0.8)
        self.assertEqual(self.calc._infer_regime(wm), "ranging")

    def test_regime_from_state_high_volatility(self):
        wm = WorldModel(state=MarketState.HIGH_VOLATILITY, regime="",
                        regime_confidence=0.8)
        self.assertEqual(self.calc._infer_regime(wm), "volatile")

    def test_low_regime_confidence_uncertain(self):
        wm = WorldModel(state=MarketState.BULL, regime="trending",
                        regime_confidence=0.1)
        self.assertEqual(self.calc._infer_regime(wm), "uncertain")


class TestIntegration(unittest.TestCase):

    def setUp(self):
        self.calc = DynamicWeightCalculator()

    def test_smc_and_volume_trending(self):
        ops = [_opinion("smc", conf=0.8), _opinion("volume", conf=0.7)]
        regs = {"smc": _reg("smc"), "volume": _reg("volume")}
        mets = {"smc": _metrics(0.85), "volume": _metrics(0.75)}
        hlth = {"smc": _health(0.95), "volume": _health(0.85)}
        wm = _world("trending")
        dist = self.calc.calculate_all(ops, regs, mets, hlth, wm)
        self.assertAlmostEqual(dist.total_weight, 1.0, places=4)
        self.assertGreater(dist.weights["smc"].final_weight, 0.0)
        self.assertGreater(dist.weights["volume"].final_weight, 0.0)

    def test_regime_affects_weights(self):
        ops = [_opinion("smc", conf=0.7), _opinion("volume", conf=0.7),
               _opinion("macro", conf=0.7)]
        regs = {o.skill_name: _reg(o.skill_name) for o in ops}
        mets = {o.skill_name: _metrics(0.6) for o in ops}
        hlth = {o.skill_name: _health(0.6) for o in ops}

        wm_trend = _world("trending")
        wm_uncertain = _world("uncertain")

        d_trend = self.calc.calculate_all(ops, regs, mets, hlth, wm_trend)
        d_uncertain = self.calc.calculate_all(ops, regs, mets, hlth, wm_uncertain)

        self.assertGreater(
            d_trend.weights["smc"].final_weight,
            d_uncertain.weights["smc"].final_weight,
        )

    def test_empty_opinions(self):
        dist = self.calc.calculate_all([], {}, {}, {})
        self.assertEqual(len(dist.weights), 0)
        self.assertEqual(dist.total_weight, 0.0)
        self.assertFalse(dist.normalized)

    def test_single_skill_weight_one(self):
        dist = self.calc.calculate_all(
            [_opinion("smc")],
            {"smc": _reg("smc")},
            {"smc": _metrics(0.8)},
            {"smc": _health(0.9)},
            _world("trending"),
        )
        self.assertAlmostEqual(dist.weights["smc"].final_weight, 1.0, places=4)
        self.assertAlmostEqual(dist.total_weight, 1.0, places=4)

    def test_reasons_populated(self):
        dist = self.calc.calculate_all(
            [_opinion("smc")],
            {"smc": _reg("smc")},
            {"smc": _metrics(0.8)},
            {"smc": _health(0.9)},
            _world("trending"),
        )
        self.assertGreater(len(dist.weights["smc"].reasons), 0)


class TestPerformance(unittest.TestCase):

    def setUp(self):
        self.calc = DynamicWeightCalculator()

    def _build_scenario(self, n: int):
        opinions = [_opinion(f"skill_{i}", conf=0.5 + (i % 5) * 0.1) for i in range(n)]
        regs = {f"skill_{i}": _reg(f"skill_{i}", cost=0.3 + (i % 4) * 0.1) for i in range(n)}
        mets = {f"skill_{i}": _metrics(0.5 + (i % 5) * 0.1) for i in range(n)}
        hlth = {f"skill_{i}": _health(0.5 + (i % 5) * 0.1) for i in range(n)}
        wm = _world("trending")
        return opinions, regs, mets, hlth, wm

    def test_10_skills(self):
        opinions, regs, mets, hlth, wm = self._build_scenario(10)
        t0 = time.perf_counter()
        dist = self.calc.calculate_all(opinions, regs, mets, hlth, wm)
        elapsed = time.perf_counter() - t0
        self.assertEqual(len(dist.weights), 10)
        self.assertAlmostEqual(dist.total_weight, 1.0, places=4)
        self.assertLess(elapsed, 2.0)

    def test_100_skills(self):
        opinions, regs, mets, hlth, wm = self._build_scenario(100)
        t0 = time.perf_counter()
        dist = self.calc.calculate_all(opinions, regs, mets, hlth, wm)
        elapsed = time.perf_counter() - t0
        self.assertEqual(len(dist.weights), 100)
        self.assertAlmostEqual(dist.total_weight, 1.0, places=4)
        self.assertLess(elapsed, 3.0)

    def test_500_skills(self):
        opinions, regs, mets, hlth, wm = self._build_scenario(500)
        t0 = time.perf_counter()
        dist = self.calc.calculate_all(opinions, regs, mets, hlth, wm)
        elapsed = time.perf_counter() - t0
        self.assertEqual(len(dist.weights), 500)
        self.assertAlmostEqual(dist.total_weight, 1.0, places=4)
        self.assertLess(elapsed, 5.0)


class TestEdgeCases(unittest.TestCase):

    def setUp(self):
        self.calc = DynamicWeightCalculator()

    def test_no_health_map(self):
        dist = self.calc.calculate_all(
            [_opinion("smc")],
            {"smc": _reg("smc")},
            {"smc": _metrics(0.8)},
            {},
            _world("trending"),
        )
        self.assertEqual(dist.weights["smc"].health_multiplier, 1.0)

    def test_no_registration_map(self):
        dist = self.calc.calculate_all(
            [_opinion("smc")], {}, {"smc": _metrics(0.8)},
            {"smc": _health(0.9)}, _world("trending"),
        )
        self.assertEqual(dist.weights["smc"].base_weight, 0.5)

    def test_no_world_model_default_uncertain(self):
        dist = self.calc.calculate_all(
            [_opinion("smc")],
            {"smc": _reg("smc")},
            {"smc": _metrics(0.8)},
            {"smc": _health(0.9)},
        )
        self.assertLess(dist.weights["smc"].regime_multiplier, 1.0)

    def test_skill_not_in_regs_map(self):
        dist = self.calc.calculate_all(
            [_opinion("unknown")], {},
            {"unknown": _metrics(0.8)},
            {"unknown": _health(0.9)},
        )
        self.assertEqual(dist.weights["unknown"].base_weight, 0.5)

    def test_infer_regime_from_state_bull(self):
        wm = WorldModel(state=MarketState.BULL, regime="", regime_confidence=0.8)
        self.assertEqual(self.calc._infer_regime(wm), "trending")

    def test_infer_regime_from_state_weak_trend(self):
        wm = WorldModel(state=MarketState.WEAK_TREND_UP, regime="", regime_confidence=0.8)
        self.assertEqual(self.calc._infer_regime(wm), "trending")

    def test_infer_regime_from_state_compression(self):
        wm = WorldModel(state=MarketState.COMPRESSION, regime="", regime_confidence=0.8)
        self.assertEqual(self.calc._infer_regime(wm), "ranging")


if __name__ == "__main__":
    unittest.main()
