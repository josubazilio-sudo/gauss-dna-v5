import os
import sys
import unittest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from trend import analyze_trend
from flex.setups import detect_setup
from flex.score import calcular_score, classificar_por_requisitos


def candles_from_closes(closes, volume=1000):
    candles = []
    prev = closes[0]
    for i, close in enumerate(closes):
        open_ = prev
        high = max(open_, close) * 1.002
        low = min(open_, close) * 0.998
        candles.append([i, open_, high, low, close, volume])
        prev = close
    return candles


class FlexQualityTests(unittest.TestCase):
    def test_emerging_trend_is_not_classified_as_lateral(self):
        closes = [100.0] * 170
        closes += [100 + i * 0.08 for i in range(1, 61)]

        trend = analyze_trend(candles_from_closes(closes))

        self.assertEqual(trend["DIRECAO"], "long")
        self.assertNotIn("Neutro", trend["TENDENCIA"])

    def test_trend_works_with_scanner_199_closed_candles(self):
        closes = [100 + i * 0.05 for i in range(199)]

        trend = analyze_trend(candles_from_closes(closes))

        self.assertEqual(trend["DIRECAO"], "long")
        self.assertIn("EMA_50", trend)

    def test_healthy_pullback_in_moderate_trend_is_institutional_setup(self):
        closes = [100 + i * 0.15 for i in range(80)]
        closes += [112.0, 111.6, 111.2, 111.5, 112.1]
        candles = candles_from_closes(closes)
        trend = {"TENDENCIA": "Alta Moderada", "DIRECAO": "long", "EMA_21": 111.0}
        smc = {"BOS": False, "CHOCH": False, "FVG": True, "ORDER_BLOCK": True, "RETESTE": True, "LIQUIDITY_SWEEP": False}
        flow = {"VOLUME_CRESCENTE": True, "DELTA": 0.04, "RVOL": 1.2}
        momentum = {"ADX": 24, "RSI": 55, "ATR": 0.6}

        setup = detect_setup(candles, trend, smc, flow, momentum)

        self.assertIsNotNone(setup)
        self.assertEqual(setup["name"], "Pullback Institucional")

    def test_classification_uses_70_80_90_thresholds(self):
        flow = {"DELTA": 0.05, "VOLUME_CRESCENTE": True, "RVOL": 1.3}
        trend = {"TENDENCIA": "Alta Moderada", "DIRECAO": "long"}

        self.assertEqual(classificar_por_requisitos(70, 22, 0.9, 60, flow, "long", "UP", trend, 1)[0], "BRONZE")
        self.assertEqual(classificar_por_requisitos(80, 25, 1.0, 65, flow, "long", "UP", trend, 1)[0], "PRATA")
        self.assertEqual(classificar_por_requisitos(90, 30, 1.1, 70, flow, "long", "UP", trend, 1)[0], "OURO")
        self.assertIsNone(classificar_por_requisitos(69, 30, 1.5, 80, flow, "long", "UP", trend, 1)[0])

    def test_institutional_score_requires_confluence_not_single_indicator(self):
        weak_score = calcular_score(
            {"DIRECAO": "lateral", "TENDENCIA": "Mercado Neutro"},
            {"VOLUME_CRESCENTE": True, "DELTA": 0.08, "RVOL": 2.5},
            {"ADX": 20, "RSI": 50, "ATR": 1.0},
            {"BOS": False, "CHOCH": False, "LIQUIDITY_SWEEP": False, "ORDER_BLOCK": False, "FVG": False, "ESTRUTURA_OK": False},
            {"ATR_COMPRESSAO": False},
            "UP",
            "long",
            1,
            follow_through_pct=5,
            volume_24h=50_000_000,
            timing_index=70,
        )
        strong_score = calcular_score(
            {"DIRECAO": "long", "TENDENCIA": "Alta Moderada"},
            {"VOLUME_CRESCENTE": True, "DELTA": 0.05, "RVOL": 1.25},
            {"ADX": 28, "RSI": 55, "ATR": 1.0},
            {"BOS": True, "CHOCH": False, "LIQUIDITY_SWEEP": True, "ORDER_BLOCK": True, "FVG": True, "RETESTE": True, "ESTRUTURA_OK": True},
            {"ATR_COMPRESSAO": False},
            "UP",
            "long",
            2,
            follow_through_pct=5,
            volume_24h=50_000_000,
            timing_index=75,
        )

        self.assertLess(weak_score["score_total"], 70)
        self.assertGreaterEqual(strong_score["score_total"], 80)


if __name__ == "__main__":
    unittest.main()
