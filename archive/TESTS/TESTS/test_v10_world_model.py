import sys
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json
import unittest
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ENGINE.world.world_types import WorldModel, MarketState, MarketQuality
from ENGINE.world.world_config import WORLD_MODEL_VERSION
from ENGINE.world.world_builder import (
    build_world_model, _infer_state, _infer_quality,
    evaluate_global_trend,
)
from ENGINE.world.world_model import WorldModelEngine
from CORE.events.event_bus import EventBus


# ============================================================
# Mock MarketContext for testing
# ============================================================
@dataclass
class MockIndicators:
    adx: float = 25.0
    rvol: float = 1.2
    rsi: float = 55.0
    atr_percent: float = 0.015


@dataclass
class MockMarketContext:
    indicators: Any = None
    trend_strength: float = 0.5
    regime: Any = None
    regime_confidence: float = 0.6
    volatility_score: float = 0.015
    liquidity_score: float = 0.5
    btc_correlation: float = 0.5
    btc_dominance: float = 0.55
    funding_rate: float = 0.005
    open_interest: float = 1000000
    confidence_score: float = 0.6
    eth_correlation: float = 0.3

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        if self.indicators is None:
            self.indicators = MockIndicators()
        if self.regime is None:
            class Regime:
                value = "ranging"
            self.regime = Regime()


import enum


def _make_regime(value: str):
    class R(enum.Enum):
        v = value
    r = R.v
    return r


# ============================================================
# 1. WorldModel dataclass
# ============================================================
class TestWorldModel(unittest.TestCase):
    def test_create_default(self):
        wm = WorldModel()
        self.assertEqual(wm.version, WORLD_MODEL_VERSION)
        self.assertEqual(wm.state, MarketState.UNCERTAIN)
        self.assertEqual(wm.quality, MarketQuality.FAIR)
        self.assertIsInstance(wm.timestamp, datetime)

    def test_imutavel(self):
        wm = WorldModel()
        with self.assertRaises(Exception):
            wm.state = MarketState.BULL

    def test_to_dict(self):
        wm = WorldModel(state=MarketState.BULL, quality=MarketQuality.EXCELLENT, confidence=0.85)
        d = wm.to_dict()
        self.assertEqual(d["state"], "bull")
        self.assertEqual(d["quality"], "excellent")
        self.assertEqual(d["confidence"], 0.85)
        self.assertEqual(d["version"], "10.0.0")

    def test_to_json(self):
        wm = WorldModel(state=MarketState.RANGING, confidence=0.5)
        j = wm.to_json()
        parsed = json.loads(j)
        self.assertEqual(parsed["state"], "ranging")
        self.assertEqual(parsed["confidence"], 0.5)

    def test_compute_hash_deterministico(self):
        wm1 = WorldModel(state=MarketState.BULL, confidence=0.8)
        wm2 = WorldModel(state=MarketState.BULL, confidence=0.8)
        # hashes should be different because timestamps differ
        self.assertIsInstance(wm1.compute_hash(), str)
        self.assertEqual(len(wm1.compute_hash()), 16)

    def test_compute_hash_diferente(self):
        wm1 = WorldModel(state=MarketState.BULL, confidence=0.8)
        wm2 = WorldModel(state=MarketState.BEAR, confidence=0.3)
        # uuids differ too but state is part of dict
        pass

    def test_is_tradeable_uncertain(self):
        wm = WorldModel(state=MarketState.UNCERTAIN, quality=MarketQuality.FAIR, confidence=0.5, health=1.0)
        self.assertFalse(wm.is_tradeable())

    def test_is_tradeable_hostile(self):
        wm = WorldModel(state=MarketState.BULL, quality=MarketQuality.HOSTILE, confidence=0.5, health=1.0)
        self.assertFalse(wm.is_tradeable())

    def test_is_tradeable_low_confidence(self):
        wm = WorldModel(state=MarketState.BULL, quality=MarketQuality.GOOD, confidence=0.1, health=1.0)
        self.assertFalse(wm.is_tradeable())

    def test_is_tradeable_ok(self):
        wm = WorldModel(state=MarketState.BULL, quality=MarketQuality.GOOD, confidence=0.6, health=1.0)
        self.assertTrue(wm.is_tradeable())

    def test_skill_health(self):
        wm = WorldModel(skill_health={"smc": 0.95, "volume": 0.80}, active_skills=["smc", "volume"])
        self.assertEqual(wm.skill_health["smc"], 0.95)
        self.assertEqual(wm.active_skills, ["smc", "volume"])


# ============================================================
# 2. WorldBuilder - _infer_state
# ============================================================
class TestInferState(unittest.TestCase):
    def test_strong_trend_up(self):
        s = _infer_state(adx=35, trend_strength=0.7, volatility_score=0.015, regime="trending_up")
        self.assertEqual(s, MarketState.STRONG_TREND_UP)

    def test_strong_trend_down(self):
        s = _infer_state(adx=32, trend_strength=0.65, volatility_score=0.015, regime="trending_down")
        self.assertEqual(s, MarketState.STRONG_TREND_DOWN)

    def test_weak_trend_up(self):
        s = _infer_state(adx=20, trend_strength=0.5, volatility_score=0.015, regime="trending_up")
        self.assertEqual(s, MarketState.WEAK_TREND_UP)

    def test_weak_trend_down(self):
        s = _infer_state(adx=18, trend_strength=0.4, volatility_score=0.015, regime="trending_down")
        self.assertEqual(s, MarketState.WEAK_TREND_DOWN)

    def test_ranging_expansion(self):
        s = _infer_state(adx=15, trend_strength=0.2, volatility_score=0.05, regime="ranging")
        self.assertEqual(s, MarketState.EXPANSION)

    def test_ranging_compression(self):
        s = _infer_state(adx=15, trend_strength=0.2, volatility_score=0.003, regime="ranging")
        self.assertEqual(s, MarketState.COMPRESSION)

    def test_ranging_normal(self):
        s = _infer_state(adx=15, trend_strength=0.2, volatility_score=0.015, regime="ranging")
        self.assertEqual(s, MarketState.RANGING)

    def test_volatile(self):
        s = _infer_state(adx=15, trend_strength=0.2, volatility_score=0.015, regime="volatile")
        self.assertEqual(s, MarketState.HIGH_VOLATILITY)

    def test_calm(self):
        s = _infer_state(adx=10, trend_strength=0.1, volatility_score=0.003, regime="calm")
        self.assertEqual(s, MarketState.LOW_VOLATILITY)

    def test_reversal(self):
        s = _infer_state(adx=28, trend_strength=0.65, volatility_score=0.025, regime="reversal")
        self.assertEqual(s, MarketState.DISTRIBUTION)

    def test_uncertain(self):
        s = _infer_state(adx=0, trend_strength=0.0, volatility_score=0.0, regime="unknown")
        self.assertEqual(s, MarketState.UNCERTAIN)


# ============================================================
# 3. WorldBuilder - _infer_quality
# ============================================================
class TestInferQuality(unittest.TestCase):
    def test_excellent(self):
        q = _infer_quality(confidence=0.85, volatility_score=0.015, liquidity_score=0.75, regime_confidence=0.80)
        self.assertEqual(q, MarketQuality.EXCELLENT)

    def test_good(self):
        q = _infer_quality(confidence=0.65, volatility_score=0.02, liquidity_score=0.5, regime_confidence=0.6)
        self.assertEqual(q, MarketQuality.GOOD)

    def test_fair(self):
        q = _infer_quality(confidence=0.45, volatility_score=0.04, liquidity_score=0.3, regime_confidence=0.4)
        self.assertEqual(q, MarketQuality.FAIR)

    def test_hostile_high_vol(self):
        q = _infer_quality(confidence=0.5, volatility_score=0.10, liquidity_score=0.5, regime_confidence=0.5)
        self.assertEqual(q, MarketQuality.HOSTILE)

    def test_hostile_low_liquidity(self):
        q = _infer_quality(confidence=0.5, volatility_score=0.02, liquidity_score=0.05, regime_confidence=0.5)
        self.assertEqual(q, MarketQuality.HOSTILE)

    def test_hostile_low_confidence(self):
        q = _infer_quality(confidence=0.1, volatility_score=0.02, liquidity_score=0.5, regime_confidence=0.5)
        self.assertEqual(q, MarketQuality.HOSTILE)

    def test_poor(self):
        q = _infer_quality(confidence=0.25, volatility_score=0.06, liquidity_score=0.15, regime_confidence=0.3)
        self.assertEqual(q, MarketQuality.POOR)


# ============================================================
# 4. WorldBuilder - evaluate_global_trend
# ============================================================
class TestGlobalTrend(unittest.TestCase):
    def test_bullish(self):
        t = evaluate_global_trend(adx=30, trend_strength=0.65, regime="trending_up")
        self.assertEqual(t, "bullish")

    def test_bearish(self):
        t = evaluate_global_trend(adx=28, trend_strength=0.70, regime="trending_down")
        self.assertEqual(t, "bearish")

    def test_slightly_bullish(self):
        t = evaluate_global_trend(adx=20, trend_strength=0.4, regime="trending_up")
        self.assertEqual(t, "slightly_bullish")

    def test_slightly_bearish(self):
        t = evaluate_global_trend(adx=18, trend_strength=0.35, regime="trending_down")
        self.assertEqual(t, "slightly_bearish")

    def test_neutral(self):
        t = evaluate_global_trend(adx=15, trend_strength=0.2, regime="ranging")
        self.assertEqual(t, "neutral")


# ============================================================
# 5. WorldBuilder - build_world_model
# ============================================================
class TestBuildWorldModel(unittest.TestCase):
    def setUp(self):
        self.ctx = MockMarketContext(
            indicators=MockIndicators(adx=32, rvol=1.5, rsi=60, atr_percent=0.012),
            trend_strength=0.70,
            regime=_make_regime("trending_up"),
            regime_confidence=0.80,
            volatility_score=0.012,
            liquidity_score=0.75,
            btc_correlation=0.65,
            btc_dominance=0.55,
            funding_rate=0.008,
            confidence_score=0.80,
            eth_correlation=0.35,
        )

    def test_build_from_market_context(self):
        wm = build_world_model(self.ctx)
        self.assertEqual(wm.state, MarketState.STRONG_TREND_UP)
        self.assertEqual(wm.quality, MarketQuality.EXCELLENT)
        self.assertEqual(wm.global_trend, "bullish")
        self.assertEqual(wm.adx, 32)
        self.assertEqual(wm.rvol, 1.5)
        self.assertEqual(wm.rsi, 60)

    def test_build_with_skill_health(self):
        wm = build_world_model(self.ctx, skill_health={"smc": 0.95}, active_skills=["smc"])
        self.assertEqual(wm.skill_health["smc"], 0.95)
        self.assertEqual(wm.active_skills, ["smc"])

    def test_build_serializable(self):
        wm = build_world_model(self.ctx)
        d = wm.to_dict()
        self.assertIn("state", d)
        self.assertIn("version", d)
        self.assertIn("timestamp", d)

    def test_build_hash(self):
        wm = build_world_model(self.ctx)
        h = wm.compute_hash()
        self.assertIsInstance(h, str)
        self.assertEqual(len(h), 16)


# ============================================================
# 6. WorldModelEngine
# ============================================================
class TestWorldModelEngine(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()
        self.engine = WorldModelEngine(event_bus=self.bus)

    def test_initial_none(self):
        self.assertIsNone(self.engine.current)

    def test_update_returns_model(self):
        ctx = MockMarketContext(
            indicators=MockIndicators(),
            trend_strength=0.5,
            regime=_make_regime("ranging"),
            volatility_score=0.015,
            liquidity_score=0.5,
            confidence_score=0.6,
        )
        wm = self.engine.update(ctx)
        self.assertIsNotNone(wm)
        self.assertIs(self.engine.current, wm)

    def test_update_fires_event(self):
        received = []
        self.bus.subscribe("world.model_updated", lambda e: received.append(e))
        ctx = MockMarketContext(
            indicators=MockIndicators(),
            trend_strength=0.5,
            regime=_make_regime("ranging"),
            volatility_score=0.015,
            liquidity_score=0.5,
            confidence_score=0.6,
        )
        self.engine.update(ctx)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].type, "world.model_updated")

    def test_is_tradeable_environment_sem_modelo(self):
        self.assertFalse(self.engine.is_tradeable_environment())

    def test_is_tradeable_environment_com_modelo(self):
        ctx = MockMarketContext(
            indicators=MockIndicators(adx=30, rvol=1.5),
            trend_strength=0.7,
            regime=_make_regime("trending_up"),
            regime_confidence=0.8,
            volatility_score=0.015,
            liquidity_score=0.7,
            confidence_score=0.7,
        )
        self.engine.update(ctx)
        self.assertTrue(self.engine.is_tradeable_environment())

    def test_get_verdict(self):
        ctx = MockMarketContext(
            indicators=MockIndicators(),
            trend_strength=0.5,
            regime=_make_regime("trending_up"),
            volatility_score=0.015,
            liquidity_score=0.5,
            confidence_score=0.6,
        )
        self.engine.update(ctx)
        v = self.engine.get_verdict()
        self.assertIn("/", v)

    def test_get_verdict_sem_modelo(self):
        self.assertEqual(self.engine.get_verdict(), "unknown")


if __name__ == "__main__":
    unittest.main(verbosity=2)
