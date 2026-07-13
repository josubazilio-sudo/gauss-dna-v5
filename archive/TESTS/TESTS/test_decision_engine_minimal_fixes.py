import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ENGINE.decision.decision_engine import DecisionEngine
from ENGINE.scanner.scanner_config import HARD_MAX_SPREAD, FVG_MIN_GAP_BPS
from ENGINE.scanner.scanner_types import (
    Signal, ScannerScore, SignalClassification, SignalDirection,
    Pattern, PatternType, MarketStructure, StructureType, EntryZone, EntryDetails,
)
from ENGINE.scanner.scanner_patterns import detect_fvg
from ENGINE.market.market_types import Candle
from datetime import datetime, timezone


def _score():
    return ScannerScore(
        institutional_score=0.90, structural_score=0.90,
        market_score=0.90, momentum_score=0.90,
        liquidity_score=0.90, risk_score=0.20,
        confidence_score=0.90, quality_score=0.90,
        entry_score=0.90, consensus_score=0.90,
        conviction_score=0.90, flow_score=0.90,
        timing_index=0.90,
    )


def _signal(regime="trending_up", direction=SignalDirection.LONG, spread=0.0):
    scores = _score()
    structure = MarketStructure(
        structure_type=StructureType.UPTREND,
        swing_highs=[], swing_lows=[],
        structure_strength=0.80,
    )
    patterns = [
        Pattern(PatternType.BOS, direction, "1h", 100.0, 0.90, 0.80, "BOS"),
        Pattern(PatternType.ORDER_BLOCK, direction, "1h", 99.0, 0.90, 0.80, "OB", {"upper": 100.0, "lower": 98.0, "index": 10}),
    ]
    entry_details = EntryDetails(EntryZone(100.0, 98.0, 99.0, 0.90, "inside"), 0.90, True, True)
    entry_details.spread = spread
    return Signal(
        ticker="BTCUSDT", timeframe="1h",
        direction=direction,
        entry_price=100.0, stop_loss=98.0,
        take_profit_1=104.0, take_profit_2=108.0,
        risk_reward=2.0,
        scores=scores, classification=SignalClassification.OURO,
        patterns=patterns, structure=structure,
        setup="test", context="test",
        approval_reasons=[], rejection_reasons=[],
        confidence=0.90, quality=0.90,
        rvol=2.0, adx=40.0, atr_value=1.0,
        regime=regime, entry_details=entry_details,
        structure_strength=0.80,
    )


class TestDecisionEngineMinimalFixes(unittest.TestCase):
    def test_trending_up_allows_long_trend_gate(self):
        sig = _signal(regime="trending_up", direction=SignalDirection.LONG)
        sd = DecisionEngine.evaluate_signal(
            sig, entry_details=sig.entry_details,
            highs=[101.0] * 20, lows=[99.0] * 20, closes=[100.0] * 20,
        )
        self.assertTrue(sd.trend_ok, f"trend_ok should be True for trending_up+LONG, got {sd.reject_reason}")
        self.assertNotEqual(sd.reject_reason, "Trend desfavoravel (trending_up)")

    def test_trending_down_allows_short_trend_gate(self):
        sig = _signal(regime="trending_down", direction=SignalDirection.SHORT)
        sd = DecisionEngine.evaluate_signal(
            sig, entry_details=sig.entry_details,
            highs=[101.0] * 20, lows=[99.0] * 20, closes=[100.0] * 20,
        )
        self.assertTrue(sd.trend_ok, f"trend_ok should be True for trending_down+SHORT, got {sd.reject_reason}")

    def test_bullish_regime_allows_long_trend_gate(self):
        sig = _signal(regime="bullish", direction=SignalDirection.LONG)
        sd = DecisionEngine.evaluate_signal(
            sig, entry_details=sig.entry_details,
            highs=[101.0] * 20, lows=[99.0] * 20, closes=[100.0] * 20,
        )
        self.assertTrue(sd.trend_ok, f"trend_ok should be True for bullish+LONG, got {sd.reject_reason}")

    def test_bearish_regime_allows_short_trend_gate(self):
        sig = _signal(regime="bearish", direction=SignalDirection.SHORT)
        sd = DecisionEngine.evaluate_signal(
            sig, entry_details=sig.entry_details,
            highs=[101.0] * 20, lows=[99.0] * 20, closes=[100.0] * 20,
        )
        self.assertTrue(sd.trend_ok, f"trend_ok should be True for bearish+SHORT, got {sd.reject_reason}")

    def test_spread_above_hard_max_is_rejected(self):
        sig = _signal(spread=HARD_MAX_SPREAD + 0.001)
        sd = DecisionEngine.evaluate_signal(
            sig, entry_details=sig.entry_details,
            highs=[101.0] * 20, lows=[99.0] * 20, closes=[100.0] * 20,
        )
        self.assertFalse(sd.spread_ok, "spread_ok should be False when spread exceeds HARD_MAX_SPREAD")
        self.assertIn("Spread", sd.reject_reason, f"reject_reason should mention Spread, got {sd.reject_reason}")

    def test_spread_below_hard_max_passes(self):
        sig = _signal(spread=HARD_MAX_SPREAD * 0.5)
        sd = DecisionEngine.evaluate_signal(
            sig, entry_details=sig.entry_details,
            highs=[101.0] * 20, lows=[99.0] * 20, closes=[100.0] * 20,
        )
        self.assertTrue(sd.spread_ok, "spread_ok should be True when spread is below HARD_MAX_SPREAD")

    def test_no_spread_attribute_passes_spread_gate(self):
        sig = _signal()
        sig.entry_details = None
        sd = DecisionEngine.evaluate_signal(
            sig, entry_details=None,
            highs=[101.0] * 20, lows=[99.0] * 20, closes=[100.0] * 20,
        )
        self.assertTrue(sd.spread_ok, "spread_ok should be True when entry_details is None")

    def test_fvg_bearish_gap_has_short_direction(self):
        ts = datetime.now(timezone.utc)
        candles = [
            Candle(ts, open=105.0, high=106.0, low=104.0, close=105.5, volume=100),
            Candle(ts, open=105.5, high=104.0, low=103.0, close=103.5, volume=100),
            Candle(ts, open=103.5, high=101.0, low=100.0, close=100.5, volume=100),
        ]
        patterns = detect_fvg(candles, "1h")
        bearish_fvgs = [p for p in patterns if p.direction == SignalDirection.SHORT]
        self.assertGreater(len(bearish_fvgs), 0,
            "Should detect at least one bearish FVG (prev.low=104 > nxt.high=101)")

    def test_fvg_bullish_gap_has_long_direction(self):
        ts = datetime.now(timezone.utc)
        candles = [
            Candle(ts, open=100.0, high=102.0, low=99.0, close=101.0, volume=100),
            Candle(ts, open=101.0, high=103.0, low=100.5, close=102.5, volume=100),
            Candle(ts, open=102.5, high=105.0, low=103.0, close=104.0, volume=100),
        ]
        patterns = detect_fvg(candles, "1h")
        bullish_fvgs = [p for p in patterns if p.direction == SignalDirection.LONG]
        self.assertGreater(len(bullish_fvgs), 0,
            "Should detect at least one bullish FVG (prev.high=102 < nxt.low=103)")


if __name__ == "__main__":
    unittest.main()
