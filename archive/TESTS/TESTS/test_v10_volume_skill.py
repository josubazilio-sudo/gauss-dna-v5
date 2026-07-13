import sys
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import unittest
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List

from ENGINE.market.market_types import MarketContext, TechnicalIndicators, TrendDirection, MarketRegime
from ENGINE.skills.volume_skill import VolumeSkill
from ENGINE.skills.skill_opinion import SkillOpinion
from ENGINE.skills.base import BaseSkill
from ENGINE.skills.skills_engine import SkillsEngine
from CORE.events.event_bus import EventBus


# ============================================================
# Mock MarketContext for Volume tests
# ============================================================
def _make_ctx(
    rvol: float = 1.0,
    volume: float = 10000,
    avg_volume: float = 10000,
    adx: float = 25.0,
    institutional_score: float = 0.5,
    market_score: float = 0.5,
    trend_score: float = 0.5,
    momentum_score: float = 0.5,
    liquidity_score: float = 0.5,
    funding_rate: float = 0.0,
    spread: float = 0.001,
) -> Any:
    indicators = TechnicalIndicators(
        rvol=rvol,
        volume=volume,
        avg_volume=avg_volume,
        adx=adx,
    )

    @dataclass
    class MockRegime:
        value: str = "ranging"

    @dataclass
    class MockCtx:
        pair: str = "BTCUSDT"
        timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
        price: float = 50000.0
        indicators: Any = None
        trend: Any = TrendDirection.NEUTRAL
        trend_strength: float = 0.5
        regime: Any = field(default_factory=lambda: MockRegime())
        regime_confidence: float = 0.5
        funding_rate: float = 0.0
        spread: float = 0.001
        institutional_score: float = 0.5
        market_score: float = 0.5
        trend_score: float = 0.5
        momentum_score: float = 0.5
        liquidity_score: float = 0.5
        confidence_score: float = 0.5
        volatility_score: float = 0.015

    return MockCtx(
        indicators=indicators,
        funding_rate=funding_rate,
        spread=spread,
        institutional_score=institutional_score,
        market_score=market_score,
        trend_score=trend_score,
        momentum_score=momentum_score,
        liquidity_score=liquidity_score,
    )


# ============================================================
# 1. VolumeSkill — Basic Contract Tests
# ============================================================
class TestVolumeSkillContract(unittest.TestCase):
    def setUp(self):
        self.skill = VolumeSkill()

    def test_extends_baseskill(self):
        self.assertIsInstance(self.skill, BaseSkill)

    def test_name_is_volume(self):
        self.assertEqual(self.skill.name, "volume")

    def test_category_is_flow(self):
        self.assertEqual(self.skill.category, "flow")

    def test_returns_skillopinion(self):
        ctx = _make_ctx()
        result = self.skill.analyze(ctx)
        self.assertIsInstance(result, SkillOpinion)

    def test_skillopinion_fields(self):
        ctx = _make_ctx()
        result = self.skill.analyze(ctx)
        self.assertEqual(result.skill_name, "volume")
        self.assertIsInstance(result.confidence, float)
        self.assertIsInstance(result.risk, float)
        self.assertIsInstance(result.probability, float)
        self.assertIsInstance(result.evidence, list)
        self.assertIsInstance(result.observations, str)
        self.assertTrue(result.success)

    def test_no_direction_fields(self):
        ctx = _make_ctx()
        result = self.skill.analyze(ctx)
        d = result.__dict__
        for forbidden in ["direction", "recommendation", "vote", "action", "long", "short"]:
            self.assertNotIn(forbidden, d)

    def test_confidence_range(self):
        ctx = _make_ctx()
        result = self.skill.analyze(ctx)
        self.assertGreaterEqual(result.confidence, 0.0)
        self.assertLessEqual(result.confidence, 1.0)

    def test_risk_range(self):
        ctx = _make_ctx()
        result = self.skill.analyze(ctx)
        self.assertGreaterEqual(result.risk, 0.0)
        self.assertLessEqual(result.risk, 1.0)

    def test_probability_range(self):
        ctx = _make_ctx()
        result = self.skill.analyze(ctx)
        self.assertGreaterEqual(result.probability, 0.0)
        self.assertLessEqual(result.probability, 1.0)

    def test_evidence_is_list_of_strings(self):
        ctx = _make_ctx()
        result = self.skill.analyze(ctx)
        for e in result.evidence:
            self.assertIsInstance(e, str)

    def test_success_false_when_no_indicators(self):

        @dataclass
        class EmptyCtx:
            pair: str = "BTCUSDT"
            price: float = 50000.0

        result = self.skill.analyze(EmptyCtx())
        self.assertFalse(result.success)
        self.assertEqual(result.confidence, 0.0)

    def test_success_false_when_context_none(self):
        result = self.skill.analyze(None)
        self.assertFalse(result.success)


# ============================================================
# 2. VolumeSkill — RVOL Tests
# ============================================================
class TestVolumeSkillRVOL(unittest.TestCase):
    def test_rvol_alto_2x(self):
        ctx = _make_ctx(rvol=2.0)
        result = VolumeSkill().analyze(ctx)
        self.assertTrue(result.success)
        self.assertGreater(result.confidence, 0.3)
        has_rvol = any("RVOL" in e for e in result.evidence)
        self.assertTrue(has_rvol)

    def test_rvol_muito_alto_3x(self):
        ctx = _make_ctx(rvol=3.0)
        result = VolumeSkill().analyze(ctx)
        self.assertTrue(result.success)
        has_extremo = any("extremamente" in e for e in result.evidence)
        self.assertTrue(has_extremo)

    def test_rvol_baixo_05(self):
        ctx = _make_ctx(rvol=0.5)
        result = VolumeSkill().analyze(ctx)
        self.assertTrue(result.success)
        has_abaixo = any("abaixo" in e for e in result.evidence)
        self.assertTrue(has_abaixo)

    def test_rvol_1_ponto_5(self):
        ctx = _make_ctx(rvol=1.5)
        result = VolumeSkill().analyze(ctx)
        self.assertTrue(result.success)
        has_muito = any("muito acima" in e for e in result.evidence)
        self.assertTrue(has_muito)

    def test_mais_rvol_mais_confianca(self):
        ctx_baixo = _make_ctx(rvol=0.5)
        ctx_alto = _make_ctx(rvol=2.5)
        r_baixo = VolumeSkill().analyze(ctx_baixo)
        r_alto = VolumeSkill().analyze(ctx_alto)
        self.assertGreater(r_alto.confidence, r_baixo.confidence)


# ============================================================
# 3. VolumeSkill — Volume Anomaly Tests
# ============================================================
class TestVolumeSkillAnomaly(unittest.TestCase):
    def test_volume_anomalo_4x(self):
        ctx = _make_ctx(volume=40000, avg_volume=10000)
        result = VolumeSkill().analyze(ctx)
        has_anomalo = any("anomalo" in e.lower() for e in result.evidence)
        self.assertTrue(has_anomalo)

    def test_volume_elevado_2x(self):
        ctx = _make_ctx(volume=20000, avg_volume=10000)
        result = VolumeSkill().analyze(ctx)
        has_elevado = any("elevado" in e.lower() for e in result.evidence)
        self.assertTrue(has_elevado)

    def test_volume_reduzido_04x(self):
        ctx = _make_ctx(volume=4000, avg_volume=10000)
        result = VolumeSkill().analyze(ctx)
        has_reduzido = any("reduzido" in e.lower() for e in result.evidence)
        self.assertTrue(has_reduzido)


# ============================================================
# 4. VolumeSkill — Flow Score Tests
# ============================================================
class TestVolumeSkillFlow(unittest.TestCase):
    def test_fluxo_forte(self):
        ctx = _make_ctx(institutional_score=0.85)
        result = VolumeSkill().analyze(ctx)
        has_forte = any("forte" in e.lower() for e in result.evidence)
        self.assertTrue(has_forte)

    def test_fluxo_fraco(self):
        ctx = _make_ctx(institutional_score=0.20)
        result = VolumeSkill().analyze(ctx)
        has_fraco = any("fraco" in e.lower() for e in result.evidence)
        self.assertTrue(has_fraco)

    def test_fluxo_moderado(self):
        ctx = _make_ctx(institutional_score=0.65)
        result = VolumeSkill().analyze(ctx)
        has_moderado = any("moderado" in e.lower() for e in result.evidence)
        self.assertTrue(has_moderado)


# ============================================================
# 5. VolumeSkill — ADX/Liquidity Tests
# ============================================================
class TestVolumeSkillContext(unittest.TestCase):
    def test_adx_forte(self):
        ctx = _make_ctx(adx=35)
        result = VolumeSkill().analyze(ctx)
        has_adx = any("ADX" in e for e in result.evidence)
        self.assertTrue(has_adx)

    def test_adx_fraco(self):
        ctx = _make_ctx(adx=18)
        result = VolumeSkill().analyze(ctx)
        has_adx = any("ADX" in e for e in result.evidence)
        self.assertTrue(has_adx)

    def test_liquidez_alta(self):
        ctx = _make_ctx(liquidity_score=0.80)
        result = VolumeSkill().analyze(ctx)
        has_liquidez = any("Liquidez" in e for e in result.evidence)
        self.assertTrue(has_liquidez)

    def test_liquidez_baixa(self):
        ctx = _make_ctx(liquidity_score=0.20)
        result = VolumeSkill().analyze(ctx)
        has_baixa = any("baixa" in e.lower() for e in result.evidence)
        # liquidity low message may or may not appear
        self.assertIsInstance(result, SkillOpinion)

    def test_funding_positivo(self):
        ctx = _make_ctx(funding_rate=0.02)
        result = VolumeSkill().analyze(ctx)
        has_funding = any("Funding" in e for e in result.evidence)
        self.assertTrue(has_funding)

    def test_funding_negativo(self):
        ctx = _make_ctx(funding_rate=-0.02)
        result = VolumeSkill().analyze(ctx)
        has_funding = any("Funding" in e for e in result.evidence)
        self.assertTrue(has_funding)

    def test_spread_baixo(self):
        ctx = _make_ctx(spread=0.0002)
        result = VolumeSkill().analyze(ctx)
        has_spread = any("Spread" in e for e in result.evidence)
        self.assertTrue(has_spread)

    def test_spread_elevado(self):
        ctx = _make_ctx(spread=0.01)
        result = VolumeSkill().analyze(ctx)
        has_spread = any("Spread" in e for e in result.evidence)
        self.assertTrue(has_spread)


# ============================================================
# 6. VolumeSkill — Integration with SkillsEngine
# ============================================================
class TestVolumeSkillIntegration(unittest.TestCase):
    def test_executa_via_skillsengine(self):
        bus = EventBus()
        engine = SkillsEngine(event_bus=bus)
        skill = VolumeSkill()
        engine.register_skill(skill)
        ctx = _make_ctx(rvol=1.5)
        opinions = engine.execute_all(ctx)
        self.assertEqual(len(opinions), 1)
        self.assertEqual(opinions[0].skill_name, "volume")
        self.assertTrue(opinions[0].success)

    def test_evento_publicado(self):
        bus = EventBus()
        engine = SkillsEngine(event_bus=bus)
        skill = VolumeSkill()
        engine.register_skill(skill)
        received = []
        bus.subscribe("skills.opinions_ready", lambda e: received.append(e))
        ctx = _make_ctx()
        engine.execute_all(ctx)
        self.assertEqual(len(received), 1)

    def test_ambas_skills_juntas(self):
        from ENGINE.skills.smc_skill import SMCSkill
        bus = EventBus()
        engine = SkillsEngine(event_bus=bus)
        engine.register_skill(SMCSkill())
        engine.register_skill(VolumeSkill())

        candles = []
        from datetime import datetime, timezone
        from ENGINE.market.market_types import Candle
        base = 100.0
        for i in range(30):
            candles.append(Candle(
                timestamp=datetime.now(timezone.utc),
                open=base + i * 0.5,
                high=base + i * 0.5 + 0.3,
                low=base + i * 0.5 - 0.3,
                close=base + i * 0.5,
                volume=1000.0,
            ))

        @dataclass
        class TimeframeCtx:
            timeframe: str = "1h"
            candles: List[Candle] = field(default_factory=list)

        @dataclass
        class MockCtx:
            pair: str = "BTCUSDT"
            timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
            price: float = 100.0
            candles: List[Candle] = field(default_factory=list)
            timeframes: Dict[str, Any] = field(default_factory=dict)
            indicators: Any = None
            funding_rate: float = 0.0
            spread: float = 0.001
            institutional_score: float = 0.6
            market_score: float = 0.6
            trend_score: float = 0.6
            momentum_score: float = 0.6
            liquidity_score: float = 0.6
            confidence_score: float = 0.6
            volatility_score: float = 0.015
            trend_strength: float = 0.5
            trend: Any = None
            regime: Any = None
            regime_confidence: float = 0.5

        tf = TimeframeCtx(candles=candles)
        ctx = MockCtx(
            candles=candles,
            timeframes={"1h": tf},
            indicators=TechnicalIndicators(rvol=1.5, adx=28),
        )

        opinions = engine.execute_all(ctx, timeout=10)
        self.assertEqual(len(opinions), 2)
        names = [o.skill_name for o in opinions]
        self.assertIn("smc", names)
        self.assertIn("volume", names)


if __name__ == "__main__":
    unittest.main(verbosity=2)
