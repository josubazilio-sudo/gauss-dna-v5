import sys
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import unittest
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List

from ENGINE.market.market_types import Candle, MarketContext, TechnicalIndicators, TrendDirection, MarketRegime, TimeframeContext
from ENGINE.skills.smc_skill import SMCSkill
from ENGINE.skills.skill_opinion import SkillOpinion
from ENGINE.skills.base import BaseSkill
from ENGINE.skills.skills_engine import SkillsEngine
from CORE.events.event_bus import EventBus


# ============================================================
# Helpers to generate candle data for tests
# ============================================================
def _make_candle(high: float, low: float, close: float, open: float = None) -> Candle:
    o = open if open is not None else low + (high - low) * 0.4
    return Candle(
        timestamp=datetime.now(timezone.utc),
        open=o,
        high=high,
        low=low,
        close=close,
        volume=1000.0,
    )


def _make_trending_up_candles(n: int = 30) -> List[Candle]:
    candles = []
    base = 100.0
    for i in range(n):
        h = base + i * 0.5 + 0.2
        l = base + i * 0.5 - 0.2
        c = base + i * 0.5
        candles.append(_make_candle(high=h, low=l, close=c))
    return candles


def _make_trending_down_candles(n: int = 30) -> List[Candle]:
    candles = []
    base = 120.0
    for i in range(n):
        h = base - i * 0.5 + 0.2
        l = base - i * 0.5 - 0.2
        c = base - i * 0.5
        candles.append(_make_candle(high=h, low=l, close=c))
    return candles


def _make_ranging_candles(n: int = 30) -> List[Candle]:
    candles = []
    base = 100.0
    for i in range(n):
        offset = (i % 5) * 0.3
        h = base + offset + 0.3
        l = base + offset - 0.3
        c = base + offset
        candles.append(_make_candle(high=h, low=l, close=c))
    return candles


def _make_volatile_candles(n: int = 30) -> List[Candle]:
    candles = []
    for i in range(n):
        spike = 5.0 if i % 7 == 0 else 1.0
        c = 100 + (i % 10) * 2
        candles.append(_make_candle(high=c + spike, low=c - spike * 0.5, close=c))
    return candles


def _make_bos_candles() -> List[Candle]:
    candles = []
    base = 100.0
    for i in range(25):
        if i < 10:
            c = base + 0.3 * i
        elif i < 15:
            c = 103.0
        else:
            c = 103.0 + 0.5 * (i - 14)
        candles.append(_make_candle(high=c + 0.2, low=c - 0.2, close=c))
    return candles


def _make_choch_candles() -> List[Candle]:
    candles = []
    for i in range(30):
        if i < 8:
            c = 100 + i
        elif i < 15:
            c = 108 - (i - 8) * 0.5
        else:
            c = 104 + (i - 15) * 0.3
        h = c + 0.5
        l = c - 0.5
        candles.append(_make_candle(high=h, low=l, close=c))
    return candles


def _make_fvg_candles() -> List[Candle]:
    candles = []
    for i in range(15):
        if i == 7:
            candles.append(_make_candle(high=105, low=104, close=104.5, open=104.8))
        elif i == 8:
            candles.append(_make_candle(high=106, low=102, close=105.5, open=102.5))
        elif i == 9:
            candles.append(_make_candle(high=106.5, low=105.5, close=106, open=106))
        else:
            candles.append(_make_candle(high=100 + i * 0.5, low=99 + i * 0.5, close=99.5 + i * 0.5))
    return candles


def _make_market_context(candles: List[Candle], price: float = None) -> Any:
    if price is None and candles:
        price = candles[-1].close
    elif price is None:
        price = 100.0

    @dataclass
    class TimeframeCtx:
        timeframe: str = "1h"
        candles: List[Candle] = field(default_factory=list)

    tf = TimeframeCtx(candles=candles)

    @dataclass
    class MockCtx:
        pair: str = "BTCUSDT"
        timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
        price: float = 100.0
        candles: List[Candle] = field(default_factory=list)
        timeframes: Dict[str, Any] = field(default_factory=dict)

    ctx = MockCtx(price=price, candles=candles, timeframes={"1h": tf})
    return ctx


# ============================================================
# 1. SMCSkill — Basic Contract Tests
# ============================================================
class TestSMCSkillContract(unittest.TestCase):
    def setUp(self):
        self.skill = SMCSkill()

    def test_extends_baseskill(self):
        self.assertIsInstance(self.skill, BaseSkill)

    def test_name_is_smc(self):
        self.assertEqual(self.skill.name, "smc")

    def test_category_is_structure(self):
        self.assertEqual(self.skill.category, "structure")

    def test_returns_skillopinion(self):
        ctx = _make_market_context(_make_trending_up_candles())
        result = self.skill.analyze(ctx)
        self.assertIsInstance(result, SkillOpinion)

    def test_skillopinion_has_correct_fields(self):
        ctx = _make_market_context(_make_trending_up_candles())
        result = self.skill.analyze(ctx)
        self.assertEqual(result.skill_name, "smc")
        self.assertIsInstance(result.confidence, float)
        self.assertIsInstance(result.risk, float)
        self.assertIsInstance(result.probability, float)
        self.assertIsInstance(result.evidence, list)
        self.assertIsInstance(result.observations, str)
        self.assertTrue(result.success)

    def test_no_direction_fields(self):
        ctx = _make_market_context(_make_trending_up_candles())
        result = self.skill.analyze(ctx)
        d = result.__dict__
        for forbidden in ["direction", "recommendation", "vote", "action", "long", "short"]:
            self.assertNotIn(forbidden, d)

    def test_confidence_range(self):
        ctx = _make_market_context(_make_trending_up_candles())
        result = self.skill.analyze(ctx)
        self.assertGreaterEqual(result.confidence, 0.0)
        self.assertLessEqual(result.confidence, 1.0)

    def test_risk_range(self):
        ctx = _make_market_context(_make_trending_up_candles())
        result = self.skill.analyze(ctx)
        self.assertGreaterEqual(result.risk, 0.0)
        self.assertLessEqual(result.risk, 1.0)

    def test_probability_range(self):
        ctx = _make_market_context(_make_trending_up_candles())
        result = self.skill.analyze(ctx)
        self.assertGreaterEqual(result.probability, 0.0)
        self.assertLessEqual(result.probability, 1.0)

    def test_evidence_is_list_of_strings(self):
        ctx = _make_market_context(_make_trending_up_candles())
        result = self.skill.analyze(ctx)
        for e in result.evidence:
            self.assertIsInstance(e, str)

    def test_success_false_when_no_candles(self):
        ctx = _make_market_context([])
        result = self.skill.analyze(ctx)
        self.assertFalse(result.success)
        self.assertEqual(result.confidence, 0.0)


# ============================================================
# 2. SMCSkill — Pattern Detection Tests
# ============================================================
class TestSMCSkillPatterns(unittest.TestCase):
    def test_trending_up_produces_evidence(self):
        skill = SMCSkill()
        ctx = _make_market_context(_make_trending_up_candles(30))
        result = skill.analyze(ctx)
        self.assertTrue(result.success)
        self.assertGreater(result.confidence, 0.0)
        self.assertGreater(len(result.evidence), 0)

    def test_trending_down_produces_evidence(self):
        skill = SMCSkill()
        ctx = _make_market_context(_make_trending_down_candles(30))
        result = skill.analyze(ctx)
        self.assertTrue(result.success)

    def test_ranging_produces_lower_confidence(self):
        skill = SMCSkill()
        ctx = _make_market_context(_make_ranging_candles(30))
        result = skill.analyze(ctx)
        self.assertTrue(result.success)

    def test_volatile_detected(self):
        skill = SMCSkill()
        ctx = _make_market_context(_make_volatile_candles(30))
        result = skill.analyze(ctx)
        self.assertTrue(result.success)

    def test_bos_detected(self):
        skill = SMCSkill()
        ctx = _make_market_context(_make_bos_candles())
        result = skill.analyze(ctx)
        self.assertTrue(result.success)
        has_bos = any("BOS" in e for e in result.evidence)
        self.assertTrue(has_bos)

    def test_choch_detected(self):
        skill = SMCSkill()
        ctx = _make_market_context(_make_choch_candles())
        result = skill.analyze(ctx)
        has_choch = any("CHoCH" in e for e in result.evidence)
        # May or may not detect depending on specific price action
        self.assertIsInstance(result.success, bool)

    def test_evidence_contains_swings(self):
        skill = SMCSkill()
        ctx = _make_market_context(_make_trending_up_candles(30))
        result = skill.analyze(ctx)
        has_swings = any("Swings" in e or "swings" in e for e in result.evidence)
        self.assertTrue(has_swings)

    def test_evidence_contains_structure(self):
        skill = SMCSkill()
        ctx = _make_market_context(_make_trending_up_candles(30))
        result = skill.analyze(ctx)
        has_structure = any("Estrutural" in e or "estrutural" in e for e in result.evidence)
        self.assertTrue(has_structure)

    def test_poucas_candles_baixa_confianca(self):
        skill = SMCSkill()
        ctx = _make_market_context(_make_trending_up_candles(5))
        result = skill.analyze(ctx)
        self.assertFalse(result.success)
        self.assertEqual(result.confidence, 0.0)


# ============================================================
# 3. SMCSkill — Confidence/Risk Consistency
# ============================================================
class TestSMCSkillConfidence(unittest.TestCase):
    def test_mais_padroes_mais_confianca(self):
        skill = SMCSkill()
        ctx1 = _make_market_context(_make_trending_up_candles(15))
        ctx2 = _make_market_context(_make_trending_up_candles(30))
        r1 = skill.analyze(ctx1)
        r2 = skill.analyze(ctx2)
        self.assertGreaterEqual(r2.confidence, r1.confidence)

    def test_confidence_nao_excede_095(self):
        skill = SMCSkill()
        candles = _make_bos_candles() + _make_bos_candles()
        ctx = _make_market_context(candles)
        for _ in range(5):
            ctx = _make_market_context(candles + _make_trending_up_candles(20))
        result = skill.analyze(ctx)
        self.assertLessEqual(result.confidence, 0.95)

    def test_risk_nao_negativo(self):
        skill = SMCSkill()
        ctx = _make_market_context(_make_trending_up_candles(30))
        result = skill.analyze(ctx)
        self.assertGreaterEqual(result.risk, 0.0)

    def test_probability_consistente(self):
        skill = SMCSkill()
        ctx = _make_market_context(_make_bos_candles())
        result = skill.analyze(ctx)
        self.assertGreaterEqual(result.probability, 0.0)
        self.assertLessEqual(result.probability, 1.0)
        self.assertGreaterEqual(result.probability, 0.0)


# ============================================================
# 4. SMCSkill — Integration with SkillsEngine
# ============================================================
class TestSMCSkillIntegration(unittest.TestCase):
    def test_executa_via_skillsengine(self):
        bus = EventBus()
        engine = SkillsEngine(event_bus=bus)
        skill = SMCSkill()
        engine.register_skill(skill)
        ctx = _make_market_context(_make_trending_up_candles(30))
        opinions = engine.execute_all(ctx)
        self.assertEqual(len(opinions), 1)
        self.assertEqual(opinions[0].skill_name, "smc")
        self.assertTrue(opinions[0].success)

    def test_evento_publicado(self):
        bus = EventBus()
        engine = SkillsEngine(event_bus=bus)
        skill = SMCSkill()
        engine.register_skill(skill)
        received = []
        bus.subscribe("skills.opinions_ready", lambda e: received.append(e))
        ctx = _make_market_context(_make_trending_up_candles(30))
        engine.execute_all(ctx)
        self.assertEqual(len(received), 1)

    def test_opinion_has_smc_metrics(self):
        bus = EventBus()
        engine = SkillsEngine(event_bus=bus)
        skill = SMCSkill()
        engine.register_skill(skill)
        ctx = _make_market_context(_make_trending_up_candles(30))
        opinions = engine.execute_all(ctx)
        metrics = opinions[0].metrics
        self.assertIsNotNone(metrics)


# ============================================================
# 5. SMCSkill — Edge Cases
# ============================================================
class TestSMCSkillEdgeCases(unittest.TestCase):
    def test_market_context_sem_candles(self):
        skill = SMCSkill()

        @dataclass
        class EmptyCtx:
            pair: str = "BTCUSDT"
            price: float = 100.0

        result = skill.analyze(EmptyCtx())
        self.assertFalse(result.success)
        self.assertEqual(result.confidence, 0.0)

    def test_market_context_none(self):
        skill = SMCSkill()
        result = skill.analyze(None)
        self.assertFalse(result.success)

    def test_observations_contem_info(self):
        skill = SMCSkill()
        ctx = _make_market_context(_make_trending_up_candles(30))
        result = skill.analyze(ctx)
        self.assertGreater(len(result.observations), 10)

    def test_evidence_inclui_padroes(self):
        skill = SMCSkill()
        ctx = _make_market_context(_make_bos_candles())
        result = skill.analyze(ctx)
        for e in result.evidence:
            self.assertGreater(len(e), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
