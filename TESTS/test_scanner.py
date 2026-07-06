import unittest
import sys
import math
import time
import random
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ENGINE.market.market_types import Candle, MarketContext, TechnicalIndicators, TrendDirection, MarketRegime
from ENGINE.market.market_engine import MarketEngine
from ENGINE.scanner.scanner_types import (
    Pattern, PatternType, SignalDirection, SignalClassification,
    MarketStructure, StructureType, SwingPoint, ScannerScore, Signal, ScanReport,
)
from ENGINE.scanner.scanner_config import (
    SCORE_THRESHOLD_OURO_SUPREMO, SCORE_THRESHOLD_OURO, SCORE_THRESHOLD_PRATA,
    DEFAULT_TIMEFRAMES, SWING_LOOKBACK,
)
from ENGINE.scanner.scanner_patterns import (
    find_swing_points, detect_bos, detect_choch, detect_order_blocks,
    detect_fvg, detect_liquidity_sweeps, scan_all_patterns,
)
from ENGINE.scanner.scanner_structure import analyze_structure
from ENGINE.scanner.scanner_scoring import (
    score_structural, score_momentum, score_liquidity, score_risk,
    score_confidence, score_institutional, compute_quality_score,
    classify_signal, check_quality_gate, compute_all_scanner_scores,
)
from ENGINE.scanner.scanner_signal import build_signal
from ENGINE.scanner.scanner_ranker import rank_signals, filter_by_threshold, pipeline
from ENGINE.scanner.scanner_engine import ScannerEngine


random.seed(42)


import random
random.seed(42)


def make_candle(close: float, high: float = None, low: float = None,
                open_p: float = None, volume: float = 1000.0) -> Candle:
    high = high or close * 1.01
    low = low or close * 0.99
    open_p = open_p or close
    return Candle(timestamp=datetime.now(timezone.utc), open=open_p, high=high, low=low, close=close, volume=volume)


def uptrend_candles(n: int = 100, start: float = 100.0, step: float = 1.0, vol: float = 1000.0) -> list[Candle]:
    candles = []
    price = start
    for i in range(n):
        price += step + random.uniform(-0.5, 0.5)
        high = price + step * 0.8 + random.uniform(0, step * 0.5)
        low = price - step * 0.5 - random.uniform(0, step * 0.3)
        candles.append(make_candle(price, high, max(low, price * 0.9), price - step * 0.2, vol))
    return candles


def ranging_candles(n: int = 100, center: float = 100.0, vol: float = 800.0) -> list[Candle]:
    candles, price = [], center
    for _ in range(n):
        price += random.uniform(-0.4, 0.4)
        candles.append(make_candle(price, price * 1.003, price * 0.997, price - random.uniform(-0.2, 0.2),
                                    vol * (0.8 + 0.4 * random.random())))
    return candles


def _make_market_context() -> MarketContext:
    return MarketContext(
        pair="TESTUSDT", timestamp=datetime.now(timezone.utc), price=100.0,
        indicators=TechnicalIndicators(atr=1.0, atr_percent=0.01, adx=30, rsi=55, rvol=1.5,
                                        bb_width=0.04, volume=1000, avg_volume=800),
        trend=TrendDirection.BULLISH, trend_strength=0.6, regime=MarketRegime.TRENDING_UP,
        regime_confidence=0.7, funding_rate=0.0, spread=0.0005,
        trend_score=0.7, momentum_score=0.6, volatility_score=0.6,
        liquidity_score=0.8, risk_score=0.7, confidence_score=0.6,
        institutional_score=0.65, market_score=0.65,
    )


# ============================================================
# UNIT TESTS — PATTERNS
# ============================================================

class TestSwingPoints(unittest.TestCase):

    def test_find_swing_points_uptrend(self):
        candles = uptrend_candles(200, 100, 2.0, 2000)
        swings = find_swing_points(candles, 4)
        self.assertIsInstance(swings, list)

    def test_find_swings_short_data(self):
        candles = [make_candle(100.0) for _ in range(5)]
        swings = find_swing_points(candles, 5)
        self.assertEqual(len(swings), 0)


class TestBOS(unittest.TestCase):

    def test_bos_detection_uptrend(self):
        candles = uptrend_candles(200, 100, 1.5, 2000)
        swings = find_swing_points(candles, 5)
        bos_long = [p for p in detect_bos(candles, swings, "1h") if p.direction == SignalDirection.LONG]
        self.assertIsInstance(bos_long, list)

    def test_bos_no_pattern_ranging(self):
        candles = ranging_candles(60, 100, 800)
        swings = find_swing_points(candles, 5)
        patterns = detect_bos(candles, swings, "1h")
        self.assertIsInstance(patterns, list)


class TestCHoCH(unittest.TestCase):

    def test_choch_found_with_swings(self):
        candles = []
        for i in range(30):
            candles.append(make_candle(100.0 + i * 2.0, 100.0 + i * 2.0 + 1, 100.0 + i * 2.0 - 1))
        for i in range(30, 60):
            candles.append(make_candle(150.0 - i * 1.5, 150.0 - i * 1.5 + 1, 150.0 - i * 1.5 - 1))
        swings = find_swing_points(candles, 3)
        patterns = detect_choch(candles, swings, "1h")
        self.assertIsInstance(patterns, list)


class TestOrderBlocks(unittest.TestCase):

    def test_ob_detected(self):
        candles = []
        for i in range(20):
            candles.append(make_candle(100.0 + i * 0.5))
        candles.append(make_candle(108.0, 109.0, 107.0, 109.0, 2000))
        candles.append(make_candle(110.0, 111.0, 109.5, 109.0, 3000))
        patterns = detect_order_blocks(candles, "1h")
        self.assertIsInstance(patterns, list)

    def test_ob_short_data(self):
        patterns = detect_order_blocks([make_candle(100.0) for _ in range(3)], "1h")
        self.assertEqual(len(patterns), 0)


class TestFVG(unittest.TestCase):

    def test_fvg_detected(self):
        candles = [
            make_candle(100.0, 101.0, 99.0),
            make_candle(101.0, 102.0, 100.0),
            make_candle(102.0, 103.0, 101.0),
        ]
        patterns = detect_fvg(candles, "1h")
        self.assertIsInstance(patterns, list)


class TestLiquiditySweeps(unittest.TestCase):

    def test_sweep_detected(self):
        candles = []
        for i in range(15):
            candles.append(make_candle(100.0 + i * 0.3))
        for i in range(10):
            candles.append(make_candle(103.0 - i * 0.1))
        swings = find_swing_points(candles, 3)
        patterns = detect_liquidity_sweeps(candles, swings, "1h")
        self.assertIsInstance(patterns, list)


class TestScanAllPatterns(unittest.TestCase):

    def test_scan_all(self):
        candles = uptrend_candles(120, 100, 1.0, 1000)
        patterns = scan_all_patterns(candles, "1h")
        self.assertIsInstance(patterns, list)


# ============================================================
# UNIT TESTS — STRUCTURE
# ============================================================

class TestMarketStructure(unittest.TestCase):

    def test_structure_uptrend(self):
        candles = uptrend_candles(200, 100, 1.5, 1000)
        ms = analyze_structure(candles)
        self.assertIsInstance(ms, MarketStructure)
        self.assertGreater(ms.mm50, 0)

    def test_structure_has_mm(self):
        candles = uptrend_candles(250, 100, 1.0, 1000)
        ms = analyze_structure(candles)
        self.assertGreater(ms.mm50, 0)
        self.assertGreater(ms.mm200, 0)
        self.assertGreater(ms.vwap, 0)

    def test_structure_mm_distances(self):
        candles = uptrend_candles(250, 100, 1.0, 1000)
        ms = analyze_structure(candles)
        self.assertNotEqual(ms.mm50_distance, 0)
        self.assertIsInstance(ms.mm50_trend, str)


# ============================================================
# UNIT TESTS — SCORING
# ============================================================

class TestScannerScoring(unittest.TestCase):

    def test_score_structural_no_patterns(self):
        ms = MarketStructure(structure_type=StructureType.UPTREND, swing_highs=[], swing_lows=[], structure_strength=0.5)
        s = score_structural(ms, [])
        self.assertGreaterEqual(s, 0)
        self.assertLessEqual(s, 1)

    def test_score_structural_with_patterns(self):
        ms = MarketStructure(structure_type=StructureType.UPTREND, swing_highs=[], swing_lows=[], structure_strength=0.7)
        pats = [Pattern(PatternType.BOS, SignalDirection.LONG, "1h", 100, 0.8, 0.6, "test")]
        s = score_structural(ms, pats)
        self.assertGreater(s, 0.3)

    def test_score_momentum(self):
        s = score_momentum(55, 1.5)
        self.assertGreaterEqual(s, 0)
        self.assertLessEqual(s, 1)

    def test_score_liquidity(self):
        s = score_liquidity(0.8, 0.0005)
        self.assertGreater(s, 0.5)

    def test_score_risk(self):
        s = score_risk(0.008, 0.8, 0.6)
        self.assertGreaterEqual(s, 0)
        self.assertLessEqual(s, 1)

    def test_score_confidence_high(self):
        ms = MarketStructure(structure_type=StructureType.UPTREND, swing_highs=[], swing_lows=[], structure_strength=0.7)
        pats = [Pattern(PatternType.BOS, SignalDirection.LONG, "1h", 100, 0.8, 0.6, "test"),
                Pattern(PatternType.FVG, SignalDirection.LONG, "1h", 101, 0.7, 0.5, "test"),
                Pattern(PatternType.ORDER_BLOCK, SignalDirection.LONG, "1h", 99, 0.75, 0.6, "test")]
        s = score_confidence(pats, ms, TrendDirection.BULLISH, 0.7)
        self.assertGreater(s, 0.4)

    def test_score_institutional(self):
        s = score_institutional(0.7, 0.65, 0.6, 0.8, 0.7, 0.6)
        self.assertGreaterEqual(s, 0)
        self.assertLessEqual(s, 1)

    def test_quality_score(self):
        sc = ScannerScore(institutional_score=0.7, structural_score=0.7, market_score=0.65,
                          momentum_score=0.6, liquidity_score=0.8, risk_score=0.7, confidence_score=0.6)
        q = compute_quality_score(sc)
        self.assertGreaterEqual(q, 0)
        self.assertLessEqual(q, 1)

    def test_classify_ouro_supremo(self):
        sc = ScannerScore(quality_score=0.92)
        self.assertEqual(classify_signal(sc), SignalClassification.OURO_SUPREMO)

    def test_classify_ouro(self):
        sc = ScannerScore(quality_score=0.80)
        self.assertEqual(classify_signal(sc), SignalClassification.OURO)

    def test_classify_prata(self):
        sc = ScannerScore(quality_score=0.65)
        self.assertEqual(classify_signal(sc), SignalClassification.PRATA)

    def test_classify_bronze(self):
        sc = ScannerScore(quality_score=0.50)
        self.assertEqual(classify_signal(sc), SignalClassification.BRONZE)

    def test_classify_reprovado(self):
        sc = ScannerScore(quality_score=0.30)
        self.assertEqual(classify_signal(sc), SignalClassification.REPROVADO)

    def test_quality_gate_passes(self):
        sc = ScannerScore(quality_score=0.75, market_score=0.6, risk_score=0.5, confidence_score=0.6)
        passed, reasons = check_quality_gate(sc)
        self.assertTrue(passed)

    def test_quality_gate_fails(self):
        sc = ScannerScore(quality_score=0.40, market_score=0.3, risk_score=0.8, confidence_score=0.3)
        passed, reasons = check_quality_gate(sc)
        self.assertFalse(passed)
        self.assertGreater(len(reasons), 0)

    def test_compute_all_scores(self):
        ms = MarketStructure(structure_type=StructureType.UPTREND, swing_highs=[], swing_lows=[], structure_strength=0.6)
        pats = [Pattern(PatternType.BOS, SignalDirection.LONG, "1h", 100, 0.8, 0.6, "test")]
        scores = compute_all_scanner_scores(ms, pats, 0.65, 0.7, 55, 1.5, 0.01, 0.8, 0.0005,
                                             TrendDirection.BULLISH, 0.7)
        self.assertIsInstance(scores, ScannerScore)
        self.assertGreater(scores.quality_score, 0)


# ============================================================
# UNIT TESTS — SIGNAL BUILDER
# ============================================================

class TestSignalBuilder(unittest.TestCase):

    def test_build_signal_long(self):
        ms = MarketStructure(structure_type=StructureType.UPTREND, swing_highs=[], swing_lows=[], structure_strength=0.6)
        pats = [Pattern(PatternType.BOS, SignalDirection.LONG, "1h", 100, 0.8, 0.6, "test")]
        sc = ScannerScore(quality_score=0.75)
        sig = build_signal("BTCUSDT", "1h", SignalDirection.LONG, pats, ms, sc,
                           SignalClassification.OURO, 100.0, atr=1.5)
        self.assertEqual(sig.ticker, "BTCUSDT")
        self.assertEqual(sig.direction, SignalDirection.LONG)
        self.assertGreater(sig.risk_reward, 0)
        self.assertGreater(sig.entry_price, 0)
        self.assertGreater(sig.stop_loss, 0)
        self.assertGreater(sig.take_profit_1, 0)

    def test_build_signal_short(self):
        ms = MarketStructure(structure_type=StructureType.DOWNTREND, swing_highs=[], swing_lows=[], structure_strength=0.5)
        pats = [Pattern(PatternType.FVG, SignalDirection.SHORT, "1h", 100, 0.7, 0.5, "test")]
        sc = ScannerScore(quality_score=0.65)
        sig = build_signal("ETHUSDT", "1h", SignalDirection.SHORT, pats, ms, sc,
                           SignalClassification.PRATA, 150.0, atr=2.0)
        self.assertEqual(sig.direction, SignalDirection.SHORT)
        self.assertGreater(sig.stop_loss, sig.entry_price)

    def test_signal_to_dict(self):
        ms = MarketStructure(structure_type=StructureType.UPTREND, swing_highs=[], swing_lows=[], structure_strength=0.6)
        pats = [Pattern(PatternType.ORDER_BLOCK, SignalDirection.LONG, "1h", 100, 0.75, 0.6, "test")]
        sc = ScannerScore(quality_score=0.80)
        sig = build_signal("SOLUSDT", "4h", SignalDirection.LONG, pats, ms, sc,
                           SignalClassification.OURO, 50.0, atr=0.5)
        d = sig.to_dict()
        self.assertEqual(d["ticker"], "SOLUSDT")
        self.assertIn("direction", d)
        self.assertIn("scores", d)
        self.assertIn("patterns", d)


# ============================================================
# UNIT TESTS — RANKER
# ============================================================

class TestRanker(unittest.TestCase):

    def _make_signal(self, quality: float) -> Signal:
        ms = MarketStructure(structure_type=StructureType.UPTREND, swing_highs=[], swing_lows=[], structure_strength=0.5)
        sc = ScannerScore(quality_score=quality)
        return build_signal("TEST", "1h", SignalDirection.LONG, [], ms, sc, SignalClassification.PRATA, 100.0)

    def test_rank_signals(self):
        s1 = self._make_signal(0.5)
        s2 = self._make_signal(0.8)
        s3 = self._make_signal(0.6)
        ranked = rank_signals([s1, s2, s3])
        self.assertEqual(ranked[0].quality, 0.8)
        self.assertEqual(ranked[-1].quality, 0.5)

    def test_filter_by_threshold(self):
        s1 = self._make_signal(0.7)
        s2 = self._make_signal(0.3)
        filtered = filter_by_threshold([s1, s2], 0.5)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].quality, 0.7)


# ============================================================
# INTEGRATION TESTS
# ============================================================

class TestScannerEngineIntegration(unittest.TestCase):

    def setUp(self):
        self.engine = ScannerEngine(timeframes=["15m", "1h", "4h"])
        self.market = MarketEngine()

    def test_scan_finds_patterns_uptrend(self):
        main = uptrend_candles(200, 100, 1.0, 1000)
        ctx = self.market.analyze("BTCUSDT", main)
        candles = {"15m": main[-100:], "1h": main[-80:], "4h": main[-60:]}
        report = self.engine.scan("BTCUSDT", candles, ctx)
        self.assertEqual(report.pair, "BTCUSDT")
        self.assertGreater(report.timeframes_analyzed, 0)
        self.assertIsInstance(report.signals, list)

    def test_scan_with_funding(self):
        main = uptrend_candles(200, 100, 1.0, 1000)
        ctx = self.market.analyze("BTCUSDT", main, funding_rate=-0.0005, spread=0.0003)
        candles = {"1h": main[-80:]}
        report = self.engine.scan("BTCUSDT", candles, ctx, funding_rate=-0.0005, spread=0.0003)
        self.assertIsInstance(report, ScanReport)

    def test_scan_empty_candles_raises(self):
        ctx = _make_market_context()
        with self.assertRaises(ValueError):
            self.engine.scan("BTCUSDT", {}, ctx)

    def test_scan_multi_timeframe(self):
        main = uptrend_candles(250, 100, 1.0, 1000)
        ctx = self.market.analyze("BTCUSDT", main)
        candles = {"5m": main[-50:], "15m": main[-100:], "1h": main[-150:], "4h": main[-200:], "1d": main}
        report = self.engine.scan("BTCUSDT", candles, ctx)
        self.assertGreaterEqual(report.timeframes_analyzed, 2)

    def test_scan_multi_pair(self):
        all_candles = {
            "BTCUSDT": {"1h": uptrend_candles(100, 100, 1.0)},
            "ETHUSDT": {"1h": uptrend_candles(100, 10, 0.1)},
        }
        contexts = {
            "BTCUSDT": self.market.analyze("BTCUSDT", all_candles["BTCUSDT"]["1h"]),
            "ETHUSDT": self.market.analyze("ETHUSDT", all_candles["ETHUSDT"]["1h"]),
        }
        results = self.engine.scan_multi(all_candles, contexts)
        self.assertIn("BTCUSDT", results)
        self.assertIn("ETHUSDT", results)

    def test_scan_report_generation(self):
        main = uptrend_candles(200, 100, 1.0, 1000)
        ctx = self.market.analyze("BTCUSDT", main)
        candles = {"1h": main[-80:]}
        report = self.engine.scan("BTCUSDT", candles, ctx)
        self.assertIsInstance(report.timestamp, datetime)
        self.assertGreaterEqual(report.duration_ms, 0)
        self.assertIsInstance(report.to_dict(), dict)

    def test_scan_last_report(self):
        main = uptrend_candles(200, 100, 1.0, 1000)
        ctx = self.market.analyze("BTCUSDT", main)
        candles = {"1h": main[-80:]}
        r1 = self.engine.scan("BTCUSDT", candles, ctx)
        r2 = self.engine.last_scan()
        self.assertEqual(r1.pair, r2.pair)


class TestScannerSignalFiltering(unittest.TestCase):

    def test_pipeline_filters_low_quality(self):
        ms = MarketStructure(structure_type=StructureType.UPTREND, swing_highs=[], swing_lows=[], structure_strength=0.5)
        p1 = [Pattern(PatternType.BOS, SignalDirection.LONG, "1h", 100, 0.8, 0.6, "good")]
        s1 = build_signal("A", "1h", SignalDirection.LONG, p1, ms, ScannerScore(quality_score=0.85),
                          SignalClassification.OURO, 100.0)
        s2 = build_signal("B", "1h", SignalDirection.LONG, [], ms, ScannerScore(quality_score=0.30),
                          SignalClassification.REPROVADO, 100.0)
        result = pipeline([s1, s2])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].ticker, "A")


# ============================================================
# PERFORMANCE TEST
# ============================================================

class TestScannerPerformance(unittest.TestCase):

    def test_scan_under_30s(self):
        engine = ScannerEngine(timeframes=["15m", "1h"])
        candles = {"15m": uptrend_candles(200, 100, 1.0, 1000),
                   "1h": uptrend_candles(150, 100, 1.0, 1000)}
        ctx = _make_market_context()
        start = time.time()
        for _ in range(10):
            engine.scan("TEST", candles, ctx)
        elapsed = time.time() - start
        avg_ms = elapsed / 10 * 1000
        self.assertLess(avg_ms, 1000, f"Average scan {avg_ms:.1f}ms exceeds 1s")

    def test_scan_multi_timeframe_under_30s(self):
        engine = ScannerEngine(timeframes=["5m", "15m", "1h", "4h", "1d"])
        candles = {tf: uptrend_candles(100 + i * 20, 100, 1.0) for i, tf in enumerate(["5m", "15m", "1h", "4h", "1d"])}
        ctx = _make_market_context()
        start = time.time()
        report = engine.scan("TEST", candles, ctx)
        elapsed = time.time() - start
        self.assertLess(elapsed, 3.0, f"5-timeframe scan took {elapsed:.2f}s")


# ============================================================
# STRESS TEST
# ============================================================

class TestScannerStress(unittest.TestCase):

    def test_large_input_stress(self):
        engine = ScannerEngine(timeframes=["1h"])
        candles = {"1h": uptrend_candles(5000, 100, 1.0, 1000)}
        ctx = _make_market_context()
        start = time.time()
        report = engine.scan("STRESS", candles, ctx)
        elapsed = time.time() - start
        self.assertLess(elapsed, 5.0, f"5000 candles took {elapsed:.2f}s")

    def test_10_timeframes_stress(self):
        engine = ScannerEngine(timeframes=[f"tf_{i}" for i in range(10)])
        candles = {f"tf_{i}": uptrend_candles(100, 100, 1.0) for i in range(10)}
        ctx = _make_market_context()
        start = time.time()
        report = engine.scan("STRESS", candles, ctx)
        elapsed = time.time() - start
        self.assertLess(elapsed, 5.0, f"10 timeframes took {elapsed:.2f}s")

    def test_100_patterns_edge(self):
        candles = uptrend_candles(500, 100, 1.5, 2000)
        patterns = scan_all_patterns(candles, "1h")
        self.assertIsInstance(patterns, list)

    def test_edge_zero_volume(self):
        candles = {"1h": [make_candle(100.0, volume=0) for _ in range(100)]}
        engine = ScannerEngine()
        ctx = _make_market_context()
        report = engine.scan("ZERO", candles, ctx)
        self.assertEqual(report.pair, "ZERO")


if __name__ == "__main__":
    unittest.main()
