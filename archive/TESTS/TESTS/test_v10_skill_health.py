import sys
import json
import time
from datetime import datetime, timezone
from typing import List

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import unittest

from ENGINE.skills.skill_opinion import SkillMetrics
from ENGINE.skills.skill_registry import SkillRegistry, SkillRegistration
from ENGINE.skills.base import BaseSkill
from ENGINE.council.health_types import HealthScore, HealthStatus
from ENGINE.council.health_config import (
    LATENCY_THRESHOLDS,
    PENALTY_TIMEOUT_PER_UNIT,
    PENALTY_ERROR_PER_UNIT,
    REC_LATENCY_HIGH,
    REC_ERRORS,
    REC_PRECISION_LOW,
    REC_ALGORITHM,
    REC_WEIGHT_REDUCE,
    REC_AVAILABILITY_LOW,
    REC_STABILITY_LOW,
)
from ENGINE.council.skill_health import HealthScoreCalculator, HealthManager


def _metrics(
    availability: float = 1.0,
    avg_latency_ms: float = 0.0,
    historical_precision: float = 0.0,
    reliability: float = 1.0,
    recent_errors: int = 0,
    total_calls: int = 0,
    successful_calls: int = 0,
) -> SkillMetrics:
    return SkillMetrics(
        availability=availability,
        avg_latency_ms=avg_latency_ms,
        historical_precision=historical_precision,
        reliability=reliability,
        last_execution=datetime.now(timezone.utc),
        recent_errors=recent_errors,
        total_calls=total_calls,
        successful_calls=successful_calls,
    )


class TestHealthTypes(unittest.TestCase):

    def test_immutable(self):
        hs = HealthScore(
            skill_name="smc", score=0.9, availability=1.0,
            reliability=1.0, precision=0.9, latency_score=1.0,
            stability=1.0, timeout_penalty=0.0, error_penalty=0.0,
            status=HealthStatus.EXCELLENT, recommendations=[],
        )
        with self.assertRaises(AttributeError):
            hs.score = 0.5

    def test_health_status_values(self):
        self.assertEqual(HealthStatus.EXCELLENT.value, "EXCELLENT")
        self.assertEqual(HealthStatus.GOOD.value, "GOOD")
        self.assertEqual(HealthStatus.FAIR.value, "FAIR")
        self.assertEqual(HealthStatus.DEGRADED.value, "DEGRADED")
        self.assertEqual(HealthStatus.CRITICAL.value, "CRITICAL")

    def test_to_dict(self):
        hs = HealthScore(
            skill_name="smc", score=0.9, availability=1.0,
            reliability=1.0, precision=0.9, latency_score=1.0,
            stability=1.0, timeout_penalty=0.0, error_penalty=0.0,
            status=HealthStatus.EXCELLENT, recommendations=["teste"],
        )
        d = hs.to_dict()
        self.assertEqual(d["skill_name"], "smc")
        self.assertEqual(d["score"], 0.9)
        self.assertEqual(d["status"], "EXCELLENT")
        self.assertIn("recommendations", d)
        self.assertIn("computed_at", d)

    def test_to_json(self):
        hs = HealthScore(
            skill_name="vol", score=0.5, availability=0.5,
            reliability=0.5, precision=0.5, latency_score=0.5,
            stability=0.5, timeout_penalty=0.0, error_penalty=0.0,
            status=HealthStatus.FAIR, recommendations=[],
        )
        j = hs.to_json()
        parsed = json.loads(j)
        self.assertEqual(parsed["skill_name"], "vol")
        self.assertEqual(parsed["status"], "FAIR")

    def test_from_dict_roundtrip(self):
        original = HealthScore(
            skill_name="smc", score=0.85, availability=0.9,
            reliability=0.95, precision=0.8, latency_score=0.8,
            stability=0.9, timeout_penalty=0.0, error_penalty=0.0,
            status=HealthStatus.GOOD, recommendations=["ajustar"],
        )
        d = original.to_dict()
        restored = HealthScore.from_dict(d)
        self.assertEqual(restored.skill_name, original.skill_name)
        self.assertEqual(restored.score, original.score)
        self.assertEqual(restored.status, original.status)
        self.assertEqual(restored.recommendations, original.recommendations)

    def test_from_json_roundtrip(self):
        original = HealthScore(
            skill_name="vol", score=0.4, availability=0.5,
            reliability=0.4, precision=0.3, latency_score=0.2,
            stability=0.5, timeout_penalty=0.1, error_penalty=0.2,
            status=HealthStatus.DEGRADED, recommendations=[],
        )
        j = original.to_json()
        restored = HealthScore.from_json(j)
        self.assertEqual(restored.score, original.score)
        self.assertEqual(restored.status, original.status)

    def test_hash_deterministic(self):
        hs = HealthScore(
            skill_name="smc", score=0.9, availability=1.0,
            reliability=1.0, precision=0.9, latency_score=1.0,
            stability=1.0, timeout_penalty=0.0, error_penalty=0.0,
            status=HealthStatus.EXCELLENT, recommendations=[],
        )
        h1 = HealthScore.compute_hash(hs)
        h2 = HealthScore.compute_hash(hs)
        self.assertEqual(h1, h2)

    def test_hash_changes_with_different_score(self):
        hs1 = HealthScore(
            skill_name="smc", score=0.9, availability=1.0,
            reliability=1.0, precision=0.9, latency_score=1.0,
            stability=1.0, timeout_penalty=0.0, error_penalty=0.0,
            status=HealthStatus.EXCELLENT, recommendations=[],
        )
        hs2 = HealthScore(
            skill_name="smc", score=0.5, availability=1.0,
            reliability=1.0, precision=0.9, latency_score=1.0,
            stability=1.0, timeout_penalty=0.0, error_penalty=0.0,
            status=HealthStatus.GOOD, recommendations=[],
        )
        self.assertNotEqual(
            HealthScore.compute_hash(hs1),
            HealthScore.compute_hash(hs2),
        )

    def test_recommendations_list(self):
        hs = HealthScore(
            skill_name="test", score=0.5, availability=0.5,
            reliability=0.5, precision=0.5, latency_score=0.5,
            stability=0.5, timeout_penalty=0.0, error_penalty=0.0,
            status=HealthStatus.FAIR, recommendations=["rec1", "rec2"],
        )
        self.assertEqual(len(hs.recommendations), 2)


class TestHealthScoreCalculation(unittest.TestCase):

    def setUp(self):
        self.calc = HealthScoreCalculator()

    def test_perfect_metrics_excellent(self):
        m = _metrics(availability=1.0, avg_latency_ms=50,
                     historical_precision=1.0, reliability=1.0)
        hs = self.calc.calculate("smc", m)
        self.assertEqual(hs.status, HealthStatus.EXCELLENT)
        self.assertGreaterEqual(hs.score, 0.9)

    def test_perfect_metrics_score_high(self):
        m = _metrics(availability=1.0, avg_latency_ms=50,
                     historical_precision=1.0, reliability=1.0)
        hs = self.calc.calculate("smc", m)
        self.assertGreater(hs.score, 0.8)

    def test_low_availability(self):
        m = _metrics(availability=0.1, avg_latency_ms=50,
                     historical_precision=0.9, reliability=0.9)
        hs = self.calc.calculate("smc", m)
        self.assertLess(hs.availability, 0.5)
        self.assertIn(REC_WEIGHT_REDUCE, hs.recommendations)

    def test_high_precision(self):
        m = _metrics(availability=1.0, avg_latency_ms=50,
                     historical_precision=0.95, reliability=1.0)
        hs = self.calc.calculate("smc", m)
        self.assertEqual(hs.precision, 0.95)
        self.assertNotIn(REC_PRECISION_LOW, hs.recommendations)

    def test_low_precision(self):
        m = _metrics(availability=1.0, avg_latency_ms=50,
                     historical_precision=0.2, reliability=1.0)
        hs = self.calc.calculate("smc", m)
        self.assertIn(REC_PRECISION_LOW, hs.recommendations)
        self.assertIn(REC_ALGORITHM, hs.recommendations)

    def test_high_latency(self):
        m = _metrics(availability=1.0, avg_latency_ms=3000,
                     historical_precision=0.9, reliability=1.0)
        hs = self.calc.calculate("smc", m)
        self.assertLess(hs.latency_score, 0.5)
        self.assertIn(REC_LATENCY_HIGH, hs.recommendations)

    def test_low_latency(self):
        m = _metrics(availability=1.0, avg_latency_ms=10,
                     historical_precision=0.9, reliability=1.0)
        hs = self.calc.calculate("smc", m)
        self.assertEqual(hs.latency_score, 1.0)

    def test_many_errors(self):
        m = _metrics(availability=1.0, avg_latency_ms=50,
                     historical_precision=0.9, reliability=1.0,
                     recent_errors=10, total_calls=100)
        hs = self.calc.calculate("smc", m)
        self.assertGreater(hs.error_penalty, 0.0)
        self.assertIn(REC_ERRORS, hs.recommendations)

    def test_many_timeouts(self):
        m = _metrics(availability=1.0, avg_latency_ms=50,
                     historical_precision=0.9, reliability=1.0)
        hs = self.calc.calculate("smc", m, timeouts=5)
        self.assertGreater(hs.timeout_penalty, 0.0)

    def test_no_errors(self):
        m = _metrics(availability=1.0, avg_latency_ms=50,
                     historical_precision=0.9, reliability=1.0,
                     recent_errors=0, total_calls=100)
        hs = self.calc.calculate("smc", m)
        self.assertEqual(hs.error_penalty, 0.0)
        self.assertNotIn(REC_ERRORS, hs.recommendations)

    def test_no_timeouts(self):
        m = _metrics(availability=1.0, avg_latency_ms=50,
                     historical_precision=0.9, reliability=1.0)
        hs = self.calc.calculate("smc", m, timeouts=0)
        self.assertEqual(hs.timeout_penalty, 0.0)

    def test_stability_high(self):
        m = _metrics(availability=1.0, avg_latency_ms=50,
                     historical_precision=0.9, reliability=1.0,
                     recent_errors=0, total_calls=100)
        hs = self.calc.calculate("smc", m)
        self.assertGreater(hs.stability, 0.9)

    def test_stability_low(self):
        m = _metrics(availability=1.0, avg_latency_ms=50,
                     historical_precision=0.9, reliability=1.0,
                     recent_errors=40, total_calls=50)
        hs = self.calc.calculate("smc", m)
        self.assertLess(hs.stability, 0.5)
        self.assertIn(REC_STABILITY_LOW, hs.recommendations)


class TestLatencyScore(unittest.TestCase):

    def setUp(self):
        self.calc = HealthScoreCalculator()

    def test_latency_excellent(self):
        sc = self.calc._compute_latency_score(50)
        self.assertEqual(sc, 1.0)

    def test_latency_at_excellent_boundary(self):
        sc = self.calc._compute_latency_score(LATENCY_THRESHOLDS["excellent"])
        self.assertEqual(sc, 1.0)

    def test_latency_good(self):
        sc = self.calc._compute_latency_score(300)
        self.assertEqual(sc, 0.8)

    def test_latency_fair(self):
        sc = self.calc._compute_latency_score(800)
        self.assertEqual(sc, 0.5)

    def test_latency_degraded(self):
        sc = self.calc._compute_latency_score(3000)
        self.assertEqual(sc, 0.2)

    def test_latency_critical(self):
        sc = self.calc._compute_latency_score(10000)
        self.assertEqual(sc, 0.0)

    def test_latency_zero(self):
        sc = self.calc._compute_latency_score(0)
        self.assertEqual(sc, 1.0)

    def test_latency_negative(self):
        sc = self.calc._compute_latency_score(-1)
        self.assertEqual(sc, 1.0)


class TestHealthClassification(unittest.TestCase):

    def setUp(self):
        self.calc = HealthScoreCalculator()

    def test_excellent(self):
        self.assertEqual(self.calc._classify(0.95), HealthStatus.EXCELLENT)
        self.assertEqual(self.calc._classify(0.9), HealthStatus.EXCELLENT)

    def test_good(self):
        self.assertEqual(self.calc._classify(0.8), HealthStatus.GOOD)
        self.assertEqual(self.calc._classify(0.7), HealthStatus.GOOD)

    def test_fair(self):
        self.assertEqual(self.calc._classify(0.6), HealthStatus.FAIR)
        self.assertEqual(self.calc._classify(0.5), HealthStatus.FAIR)

    def test_degraded(self):
        self.assertEqual(self.calc._classify(0.4), HealthStatus.DEGRADED)
        self.assertEqual(self.calc._classify(0.3), HealthStatus.DEGRADED)

    def test_critical(self):
        self.assertEqual(self.calc._classify(0.2), HealthStatus.CRITICAL)
        self.assertEqual(self.calc._classify(0.0), HealthStatus.CRITICAL)

    def test_exactly_one(self):
        self.assertEqual(self.calc._classify(1.0), HealthStatus.EXCELLENT)

    def test_exactly_zero(self):
        self.assertEqual(self.calc._classify(0.0), HealthStatus.CRITICAL)


class TestPenalties(unittest.TestCase):

    def setUp(self):
        self.calc = HealthScoreCalculator()

    def test_timeout_penalty_scales(self):
        m = _metrics()
        hs1 = self.calc.calculate("test", m, timeouts=1)
        hs2 = self.calc.calculate("test", m, timeouts=5)
        self.assertGreater(hs2.timeout_penalty, hs1.timeout_penalty)

    def test_error_penalty_scales(self):
        m1 = _metrics(recent_errors=1, total_calls=10)
        m2 = _metrics(recent_errors=5, total_calls=10)
        hs1 = self.calc.calculate("test", m1)
        hs2 = self.calc.calculate("test", m2)
        self.assertGreater(hs2.error_penalty, hs1.error_penalty)

    def test_max_penalty_capped(self):
        m = _metrics(recent_errors=100, total_calls=100,
                     availability=1.0, avg_latency_ms=50,
                     historical_precision=1.0, reliability=1.0)
        hs = self.calc.calculate("test", m, timeouts=100)
        self.assertGreaterEqual(hs.score, 0.0)
        base = (1.0 * 0.20 + 1.0 * 0.20 + 1.0 * 0.25 + 1.0 * 0.15 + 0.0 * 0.20)
        expected = round(max(0.0, base * (1.0 - 0.80)), 4)
        self.assertEqual(hs.score, expected)

    def test_score_never_negative(self):
        m = _metrics(availability=0.0, historical_precision=0.0,
                     reliability=0.0, avg_latency_ms=99999,
                     recent_errors=100, total_calls=1)
        hs = self.calc.calculate("test", m, timeouts=100)
        self.assertGreaterEqual(hs.score, 0.0)

    def test_penalty_reduces_score(self):
        m = _metrics(availability=1.0, avg_latency_ms=50,
                     historical_precision=1.0, reliability=1.0)
        hs_no = self.calc.calculate("test", m, timeouts=0)
        hs_yes = self.calc.calculate("test", m, timeouts=10)
        self.assertGreaterEqual(hs_no.score, hs_yes.score)


class TestRecommendations(unittest.TestCase):

    def setUp(self):
        self.calc = HealthScoreCalculator()
        self.perfect = _metrics(availability=1.0, avg_latency_ms=50,
                                historical_precision=1.0, reliability=1.0)

    def test_no_recommendations_perfect(self):
        hs = self.calc.calculate("test", self.perfect)
        self.assertEqual(len(hs.recommendations), 0)

    def test_latency_recommendation(self):
        m = _metrics(availability=1.0, avg_latency_ms=3000,
                     historical_precision=1.0, reliability=1.0)
        hs = self.calc.calculate("test", m)
        self.assertIn(REC_LATENCY_HIGH, hs.recommendations)

    def test_errors_recommendation(self):
        m = _metrics(availability=1.0, avg_latency_ms=50,
                     historical_precision=1.0, reliability=1.0,
                     recent_errors=5, total_calls=10)
        hs = self.calc.calculate("test", m)
        self.assertIn(REC_ERRORS, hs.recommendations)

    def test_precision_recommendation(self):
        m = _metrics(availability=1.0, avg_latency_ms=50,
                     historical_precision=0.2, reliability=1.0)
        hs = self.calc.calculate("test", m)
        self.assertIn(REC_PRECISION_LOW, hs.recommendations)
        self.assertIn(REC_ALGORITHM, hs.recommendations)

    def test_availability_recommendation(self):
        m = _metrics(availability=0.2, avg_latency_ms=50,
                     historical_precision=0.9, reliability=1.0)
        hs = self.calc.calculate("test", m)
        self.assertIn(REC_WEIGHT_REDUCE, hs.recommendations)
        self.assertIn(REC_AVAILABILITY_LOW, hs.recommendations)

    def test_stability_recommendation(self):
        m = _metrics(availability=1.0, avg_latency_ms=50,
                     historical_precision=1.0, reliability=1.0,
                     recent_errors=30, total_calls=40)
        hs = self.calc.calculate("test", m)
        self.assertIn(REC_STABILITY_LOW, hs.recommendations)


class TestIntegrationRegistry(unittest.TestCase):

    def setUp(self):
        self.calc = HealthScoreCalculator()

    def test_with_skill_registry(self):
        registry = SkillRegistry()

        class FakeSkill(BaseSkill):
            def analyze(self, ctx, wm=None):
                pass

        skill = FakeSkill("smc", "1.0", "analysis")
        skill.metrics = _metrics(availability=0.9, avg_latency_ms=100,
                                 historical_precision=0.85, reliability=0.95)
        registry.register(skill)

        reg = registry.get_registration("smc")
        self.assertIsNotNone(reg)
        self.assertEqual(reg.name, "smc")

    def test_health_manager_integration(self):
        registry = SkillRegistry()

        class FakeSkill(BaseSkill):
            def analyze(self, ctx, wm=None):
                pass

        skill = FakeSkill("smc", "1.0", "analysis")
        skill.metrics = _metrics(availability=0.95, avg_latency_ms=80,
                                 historical_precision=0.9, reliability=0.95)
        registry.register(skill)

        mgr = HealthManager(registry)
        results = mgr.evaluate_all()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].skill_name, "smc")
        self.assertGreater(results[0].score, 0.0)

    def test_health_manager_evaluate_single(self):
        mgr = HealthManager()
        m = _metrics(availability=1.0, avg_latency_ms=50,
                     historical_precision=1.0, reliability=1.0)
        hs = mgr.evaluate("smc", m)
        self.assertEqual(hs.skill_name, "smc")
        self.assertEqual(hs.status, HealthStatus.EXCELLENT)

    def test_health_manager_cache(self):
        mgr = HealthManager()
        m = _metrics(availability=0.5, avg_latency_ms=500,
                     historical_precision=0.5, reliability=0.5)
        mgr.evaluate("test", m)
        cached = mgr.get_latest("test")
        self.assertIsNotNone(cached)
        self.assertEqual(cached.skill_name, "test")
        self.assertIsNone(mgr.get_latest("nonexistent"))

    def test_health_manager_clear_cache(self):
        mgr = HealthManager()
        m = _metrics()
        mgr.evaluate("test", m)
        self.assertIsNotNone(mgr.get_latest("test"))
        mgr.clear_cache()
        self.assertIsNone(mgr.get_latest("test"))

    def test_health_manager_no_registry(self):
        mgr = HealthManager()
        results = mgr.evaluate_all()
        self.assertEqual(len(results), 0)

    def test_registry_with_multiple_skills(self):
        registry = SkillRegistry()

        class FakeSkill(BaseSkill):
            def analyze(self, ctx, wm=None):
                pass

        for i in range(5):
            skill = FakeSkill(f"skill_{i}", "1.0", "analysis")
            skill.metrics = _metrics(availability=0.9, avg_latency_ms=100,
                                     historical_precision=0.8, reliability=0.9)
            registry.register(skill)

        mgr = HealthManager(registry)
        results = mgr.evaluate_all()
        self.assertEqual(len(results), 5)


class TestPerformance(unittest.TestCase):

    def setUp(self):
        self.calc = HealthScoreCalculator()

    def test_100_skills(self):
        t0 = time.perf_counter()
        for i in range(100):
            m = _metrics(availability=0.9, avg_latency_ms=100,
                         historical_precision=0.8, reliability=0.9,
                         recent_errors=i % 5, total_calls=100)
            self.calc.calculate(f"skill_{i}", m)
        elapsed = time.perf_counter() - t0
        self.assertLess(elapsed, 2.0)

    def test_500_skills(self):
        t0 = time.perf_counter()
        for i in range(500):
            m = _metrics(availability=0.9, avg_latency_ms=100,
                         historical_precision=0.8, reliability=0.9)
            self.calc.calculate(f"skill_{i}", m)
        elapsed = time.perf_counter() - t0
        self.assertLess(elapsed, 5.0)

    def test_1000_skills(self):
        t0 = time.perf_counter()
        for i in range(1000):
            m = _metrics(availability=0.9, avg_latency_ms=100,
                         historical_precision=0.8, reliability=0.9)
            self.calc.calculate(f"skill_{i}", m)
        elapsed = time.perf_counter() - t0
        self.assertLess(elapsed, 10.0)


class TestEdgeCases(unittest.TestCase):

    def setUp(self):
        self.calc = HealthScoreCalculator()

    def test_no_calls(self):
        m = _metrics(total_calls=0)
        hs = self.calc.calculate("test", m)
        self.assertEqual(hs.stability, 1.0)
        self.assertEqual(hs.error_penalty, 0.0)

    def test_large_metrics_values(self):
        m = _metrics(availability=1.0, avg_latency_ms=1e9,
                     historical_precision=1.0, reliability=1.0)
        hs = self.calc.calculate("test", m)
        self.assertEqual(hs.latency_score, 0.0)

    def test_exact_latency_boundaries(self):
        m = _metrics(avg_latency_ms=100)
        hs = self.calc.calculate("test", m)
        self.assertEqual(hs.latency_score, 1.0)

        m2 = _metrics(avg_latency_ms=101)
        hs2 = self.calc.calculate("test", m2)
        self.assertEqual(hs2.latency_score, 0.8)

    def test_score_not_one_with_penalties(self):
        m = _metrics(availability=1.0, avg_latency_ms=50,
                     historical_precision=1.0, reliability=1.0,
                     recent_errors=0, total_calls=100)
        hs = self.calc.calculate("test", m, timeouts=1)
        self.assertLess(hs.score, 1.0)

    def test_all_zero_metrics(self):
        m = _metrics(availability=0.0, avg_latency_ms=0.0,
                     historical_precision=0.0, reliability=0.0,
                     recent_errors=0, total_calls=0)
        hs = self.calc.calculate("test", m)
        self.assertGreaterEqual(hs.score, 0.0)

    def test_multiple_recommendations(self):
        m = _metrics(availability=0.1, avg_latency_ms=10000,
                     historical_precision=0.1, reliability=0.1,
                     recent_errors=20, total_calls=30)
        hs = self.calc.calculate("test", m)
        self.assertGreater(len(hs.recommendations), 2)


if __name__ == "__main__":
    unittest.main()
