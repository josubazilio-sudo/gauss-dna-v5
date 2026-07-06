import unittest
import sys
import math
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ENGINE.market.market_types import (
    Candle, TrendDirection, MarketRegime, RsiZone, VolatilityZone,
    MarketContext, TechnicalIndicators,
)
from ENGINE.market.market_config import (
    TREND_ADX_THRESHOLD, RSI_OVERBOUGHT, RSI_OVERSOLD,
    LIQUIDITY_SPREAD_GOOD, LIQUIDITY_FUNDING_WARN,
)
from ENGINE.market.market_trend import (
    compute_ema, compute_adx, compute_slope, analyze_trend,
)
from ENGINE.market.market_momentum import (
    compute_rsi, compute_rvol, classify_rsi, analyze_momentum,
)
from ENGINE.market.market_volatility import (
    compute_atr, compute_bollinger_bands, classify_volatility, analyze_volatility,
)
from ENGINE.market.market_liquidity import (
    score_spread, score_funding, score_volume_quality, analyze_liquidity,
)
from ENGINE.market.market_regime import classify_regime
from ENGINE.market.market_scoring import (
    score_trend, score_momentum, score_volatility,
    score_risk, score_confidence, compute_all_scores,
)
from ENGINE.market.market_engine import MarketEngine
from ENGINE.market.market_report import generate_report, generate_summary
from ENGINE.market.market_correlation import compute_correlation


def make_candle(close: float, high: float = None, low: float = None,
                open_p: float = None, volume: float = 1000.0,
                ts: datetime = None) -> Candle:
    high = high or close * 1.01
    low = low or close * 0.99
    open_p = open_p or close
    ts = ts or datetime.now(timezone.utc)
    return Candle(timestamp=ts, open=open_p, high=high, low=low, close=close, volume=volume)


def uptrend_candles(n: int = 100, start: float = 100.0, step: float = 1.0, vol: float = 1000.0) -> list[Candle]:
    candles = []
    price = start
    for i in range(n):
        price = start + i * step
        candles.append(make_candle(price, price * 1.015, price * 0.985,
                                    price - step * 0.3, vol))
    return candles


def downtrend_candles(n: int = 100, start: float = 150.0, step: float = 1.0, vol: float = 1000.0) -> list[Candle]:
    candles = []
    price = start
    for i in range(n):
        price = start - i * step
        candles.append(make_candle(price, price * 1.015, price * 0.985,
                                    price + step * 0.3, vol))
    return candles


import random
random.seed(42)

def ranging_candles(n: int = 100, center: float = 100.0, amplitude: float = 2.0, vol: float = 800.0) -> list[Candle]:
    candles = []
    price = center
    for i in range(n):
        price += random.uniform(-0.4, 0.4)
        h = price * (1.0 + 0.003 * random.random())
        l = price * (1.0 - 0.003 * random.random())
        candles.append(make_candle(price, h, l, price - random.uniform(-0.2, 0.2),
                                    vol * (0.8 + 0.4 * random.random())))
    return candles


def volatile_candles(n: int = 100, center: float = 100.0, vol_amp: float = 5.0, vol: float = 2000.0) -> list[Candle]:
    candles = []
    for i in range(n):
        price = center + vol_amp * math.sin(i * 0.5) + vol_amp * 0.5 * math.sin(i * 1.3)
        candles.append(make_candle(price, price * 1.03, price * 0.97,
                                    price - 0.5, vol * (1.5 + math.sin(i * 0.7))))
    return candles


# ============================================================
# UNIT TESTS
# ============================================================

class TestTrendAnalysis(unittest.TestCase):

    def test_ema_rising_prices(self):
        values = [float(i) for i in range(1, 101)]
        ema = compute_ema(values, 9)
        self.assertAlmostEqual(ema, 100.0, delta=5.0)

    def test_ema_constant(self):
        values = [50.0] * 100
        ema = compute_ema(values, 9)
        self.assertAlmostEqual(ema, 50.0, delta=0.01)

    def test_ema_short_data(self):
        values = [10.0, 11.0]
        ema = compute_ema(values, 9)
        self.assertAlmostEqual(ema, 11.0, delta=0.01)

    def test_adx_uptrend(self):
        candles = uptrend_candles(100, 100, 0.8, 1000)
        adx = compute_adx(candles)
        self.assertGreater(adx, TREND_ADX_THRESHOLD)

    def test_adx_downtrend(self):
        candles = downtrend_candles(100, 150, 0.8, 1000)
        adx = compute_adx(candles)
        self.assertGreater(adx, TREND_ADX_THRESHOLD)

    def test_adx_ranging(self):
        candles = ranging_candles(100, 100, 1.0, 800)
        adx = compute_adx(candles)
        self.assertLess(adx, TREND_ADX_THRESHOLD + 5)

    def test_slope_positive(self):
        candles = uptrend_candles(30, 100, 1.0, 1000)
        slope = compute_slope(candles, 10)
        self.assertGreater(slope, 0)

    def test_slope_negative(self):
        candles = downtrend_candles(30, 150, 1.0, 1000)
        slope = compute_slope(candles, 10)
        self.assertLess(slope, 0)

    def test_analyze_trend_bullish(self):
        candles = uptrend_candles(100, 100, 1.0, 1000)
        direction, strength = analyze_trend(candles)
        self.assertEqual(direction, TrendDirection.BULLISH)
        self.assertGreater(strength, 0.4)

    def test_analyze_trend_bearish(self):
        candles = downtrend_candles(100, 200, 1.0, 1000)
        direction, strength = analyze_trend(candles)
        self.assertEqual(direction, TrendDirection.BEARISH)
        self.assertGreater(strength, 0.4)

    def test_analyze_trend_neutral(self):
        candles = ranging_candles(50, 100, 1.0, 800)
        direction, strength = analyze_trend(candles)
        self.assertEqual(direction, TrendDirection.NEUTRAL)

    def test_analyze_trend_short_data(self):
        candles = [make_candle(100.0) for _ in range(10)]
        direction, strength = analyze_trend(candles)
        self.assertEqual(direction, TrendDirection.NEUTRAL)
        self.assertAlmostEqual(strength, 0.0, delta=0.01)


class TestMomentumAnalysis(unittest.TestCase):

    def test_rsi_uptrend(self):
        candles = uptrend_candles(100, 100, 1.0, 1000)
        rsi = compute_rsi(candles)
        self.assertGreater(rsi, 50)

    def test_rsi_downtrend(self):
        candles = downtrend_candles(100, 200, 1.0, 1000)
        rsi = compute_rsi(candles)
        self.assertLess(rsi, 50)

    def test_rsi_constant(self):
        candles = [make_candle(100.0) for _ in range(50)]
        rsi = compute_rsi(candles)
        self.assertAlmostEqual(rsi, 50.0, delta=10)

    def test_rsi_short_data(self):
        candles = [make_candle(100.0) for _ in range(5)]
        rsi = compute_rsi(candles)
        self.assertAlmostEqual(rsi, 50.0, delta=0.01)

    def test_rvol_above_one(self):
        candles = uptrend_candles(50, 100, 0.5, 1000)
        candles[-1] = make_candle(candles[-1].close, volume=3000.0)
        rvol = compute_rvol(candles)
        self.assertGreater(rvol, 1.0)

    def test_rvol_below_one(self):
        candles = uptrend_candles(50, 100, 0.5, 1000)
        candles[-1] = make_candle(candles[-1].close, volume=100.0)
        rvol = compute_rvol(candles)
        self.assertLess(rvol, 1.0)

    def test_classify_rsi_overbought(self):
        self.assertEqual(classify_rsi(75), RsiZone.OVERBOUGHT)
        self.assertEqual(classify_rsi(70), RsiZone.OVERBOUGHT)

    def test_classify_rsi_oversold(self):
        self.assertEqual(classify_rsi(25), RsiZone.OVERSOLD)
        self.assertEqual(classify_rsi(30), RsiZone.OVERSOLD)

    def test_classify_rsi_normal(self):
        self.assertEqual(classify_rsi(50), RsiZone.NORMAL)
        self.assertEqual(classify_rsi(45), RsiZone.NORMAL)

    def test_analyze_momentum(self):
        candles = uptrend_candles(50, 100, 0.5, 1000)
        rsi, rvol, avg_vol, vol = analyze_momentum(candles)
        self.assertGreater(rsi, 0)
        self.assertGreater(rvol, 0)
        self.assertGreater(avg_vol, 0)
        self.assertGreater(vol, 0)


class TestVolatilityAnalysis(unittest.TestCase):

    def test_atr_positive(self):
        candles = uptrend_candles(50, 100, 0.5, 1000)
        atr = compute_atr(candles)
        self.assertGreater(atr, 0)

    def test_atr_short_data(self):
        candles = [make_candle(100.0) for _ in range(5)]
        atr = compute_atr(candles)
        self.assertAlmostEqual(atr, 0.0, delta=0.01)

    def test_bollinger_bands(self):
        candles = uptrend_candles(50, 100, 0.5, 1000)
        mid, upper, lower = compute_bollinger_bands(candles)
        self.assertGreater(upper, mid)
        self.assertLess(lower, mid)
        self.assertAlmostEqual(mid, sum(c.close for c in candles[-20:]) / 20, delta=0.01)

    def test_bollinger_bands_short_data(self):
        candles = [make_candle(100.0) for _ in range(5)]
        mid, upper, lower = compute_bollinger_bands(candles, 20)
        self.assertEqual(mid, lower)
        self.assertEqual(lower, upper)

    def test_classify_volatility_low(self):
        zone = classify_volatility(0.001)
        self.assertEqual(zone, VolatilityZone.LOW)

    def test_classify_volatility_moderate(self):
        zone = classify_volatility(0.005)
        self.assertEqual(zone, VolatilityZone.MODERATE)

    def test_classify_volatility_high(self):
        zone = classify_volatility(0.015)
        self.assertEqual(zone, VolatilityZone.HIGH)

    def test_classify_volatility_extreme(self):
        zone = classify_volatility(0.025)
        self.assertEqual(zone, VolatilityZone.EXTREME)

    def test_analyze_volatility(self):
        candles = uptrend_candles(50, 100, 0.5, 1000)
        atr, atr_p, mid, up, low, bw, bp = analyze_volatility(candles)
        self.assertGreater(atr, 0)
        self.assertGreater(atr_p, 0)
        self.assertGreater(mid, 0)
        self.assertGreater(bw, 0)
        self.assertGreaterEqual(bp, 0)
        self.assertLessEqual(bp, 1)


class TestLiquidityAnalysis(unittest.TestCase):

    def test_score_spread_good(self):
        self.assertAlmostEqual(score_spread(0.0001), 1.0, delta=0.01)

    def test_score_spread_poor(self):
        self.assertAlmostEqual(score_spread(0.005), 0.1, delta=0.01)

    def test_score_funding_good(self):
        self.assertAlmostEqual(score_funding(0.001), 1.0, delta=0.05)

    def test_score_funding_bad(self):
        self.assertLess(score_funding(0.02), 0.3)

    def test_score_volume_high(self):
        self.assertAlmostEqual(score_volume_quality(2.5, 1000), 1.0, delta=0.01)

    def test_score_volume_low(self):
        self.assertLess(score_volume_quality(0.3, 1000), 0.5)

    def test_analyze_liquidity(self):
        comp, ss, fs = analyze_liquidity(0.0005, 0.001, 1.5, 1000)
        self.assertGreater(comp, 0.5)
        self.assertGreaterEqual(ss, 0)
        self.assertGreaterEqual(fs, 0)


class TestRegimeClassification(unittest.TestCase):

    def test_trending_up(self):
        regime, conf = classify_regime(
            TrendDirection.BULLISH, 0.7, 30, 0.008, 55, 0.04, 1.2,
        )
        self.assertEqual(regime, MarketRegime.TRENDING_UP)
        self.assertGreater(conf, 0.5)

    def test_trending_down(self):
        regime, conf = classify_regime(
            TrendDirection.BEARISH, 0.7, 30, 0.008, 45, 0.04, 1.2,
        )
        self.assertEqual(regime, MarketRegime.TRENDING_DOWN)
        self.assertGreater(conf, 0.5)

    def test_ranging(self):
        regime, conf = classify_regime(
            TrendDirection.NEUTRAL, 0.2, 15, 0.005, 50, 0.03, 0.8,
        )
        self.assertEqual(regime, MarketRegime.RANGING)
        self.assertGreater(conf, 0.3)

    def test_volatile(self):
        regime, conf = classify_regime(
            TrendDirection.NEUTRAL, 0.3, 18, 0.025, 50, 0.09, 2.0,
        )
        self.assertEqual(regime, MarketRegime.VOLATILE)

    def test_reversal(self):
        regime, conf = classify_regime(
            TrendDirection.BULLISH, 0.7, 35, 0.025, 25, 0.09, 2.0,
        )
        self.assertEqual(regime, MarketRegime.REVERSAL)

    def test_calm(self):
        regime, conf = classify_regime(
            TrendDirection.NEUTRAL, 0.1, 10, 0.001, 50, 0.01, 0.5,
        )
        self.assertEqual(regime, MarketRegime.CALM)


class TestScoring(unittest.TestCase):

    def test_score_trend_bullish(self):
        s = score_trend(TrendDirection.BULLISH, 0.7, 30)
        self.assertGreater(s, 0.5)
        self.assertLessEqual(s, 1.0)

    def test_score_trend_neutral(self):
        s = score_trend(TrendDirection.NEUTRAL, 0.3, 15)
        self.assertLess(s, 0.3)

    def test_score_momentum_normal(self):
        s = score_momentum(50, 1.0)
        self.assertGreater(s, 0.0)
        self.assertLessEqual(s, 1.0)

    def test_score_momentum_extreme(self):
        s = score_momentum(85, 2.5)
        self.assertGreater(s, 0.5)

    def test_score_volatility_low(self):
        s = score_volatility(0.001, 0.01)
        self.assertLess(s, 0.5)

    def test_score_volatility_moderate(self):
        s = score_volatility(0.006, 0.04)
        self.assertGreater(s, 0.5)

    def test_score_volatility_extreme(self):
        s = score_volatility(0.025, 0.1)
        self.assertLess(s, 0.5)

    def test_score_risk(self):
        s = score_risk(0.006, 0.0005, 0.001, 0.7, 0.9)
        self.assertGreater(s, 0.5)
        self.assertLessEqual(s, 1.0)

    def test_score_confidence_high(self):
        s = score_confidence(
            TrendDirection.BULLISH, MarketRegime.TRENDING_UP,
            0.8, RsiZone.NORMAL, VolatilityZone.MODERATE,
        )
        self.assertGreater(s, 0.5)

    def test_score_confidence_low_extreme(self):
        s = score_confidence(
            TrendDirection.NEUTRAL, MarketRegime.VOLATILE,
            0.3, RsiZone.NORMAL, VolatilityZone.EXTREME,
        )
        self.assertLess(s, 0.5)

    def test_compute_all_scores(self):
        scores = compute_all_scores(
            TrendDirection.BULLISH, 0.7, 30, 55, 1.5,
            0.008, 0.04, 0.0005, 0.001, 0.85,
            MarketRegime.TRENDING_UP, 0.75, RsiZone.NORMAL, VolatilityZone.MODERATE,
        )
        self.assertIn("trend_score", scores)
        self.assertIn("momentum_score", scores)
        self.assertIn("volatility_score", scores)
        self.assertIn("liquidity_score", scores)
        self.assertIn("risk_score", scores)
        self.assertIn("confidence_score", scores)
        self.assertIn("institutional_score", scores)
        self.assertIn("market_score", scores)
        for key, val in scores.items():
            self.assertGreaterEqual(val, 0.0)
            self.assertLessEqual(val, 1.0)


class TestCorrelation(unittest.TestCase):

    def test_perfect_positive(self):
        a = [1.0, 2.0, 3.0, 4.0, 5.0]
        b = [1.0, 2.0, 3.0, 4.0, 5.0]
        r = compute_correlation(a, b)
        self.assertAlmostEqual(r, 1.0, delta=0.01)

    def test_perfect_negative(self):
        a = [1.0, 2.0, 3.0, 4.0, 5.0]
        b = [5.0, 4.0, 3.0, 2.0, 1.0]
        r = compute_correlation(a, b)
        self.assertAlmostEqual(r, -1.0, delta=0.01)

    def test_no_correlation(self):
        a = [1.0, 2.0, 3.0, 4.0, 5.0]
        b = [3.0, 3.1, 2.9, 3.0, 3.1]
        r = compute_correlation(a, b)
        self.assertAlmostEqual(r, 0.0, delta=0.5)

    def test_short_data(self):
        r = compute_correlation([1.0], [2.0])
        self.assertAlmostEqual(r, 0.0, delta=0.01)


# ============================================================
# INTEGRATION TESTS
# ============================================================

class TestMarketEngineIntegration(unittest.TestCase):

    def setUp(self):
        self.engine = MarketEngine()

    def test_engine_creates_context(self):
        candles = uptrend_candles(120, 100, 1.0, 1000)
        ctx = self.engine.analyze("BTCUSDT", candles)
        self.assertIsInstance(ctx, MarketContext)
        self.assertEqual(ctx.pair, "BTCUSDT")
        self.assertGreater(ctx.price, 0)
        self.assertIn(ctx.trend, (TrendDirection.BULLISH, TrendDirection.NEUTRAL))

    def test_engine_scores_uptrend(self):
        candles = uptrend_candles(120, 100, 1.0, 1000)
        ctx = self.engine.analyze("BTCUSDT", candles,
                                   funding_rate=-0.0001, spread=0.0002,
                                   btc_correlation=0.8, eth_correlation=0.7, btc_dominance=45.0)
        self.assertGreater(ctx.market_score, 0.3)
        self.assertGreater(ctx.trend_score, 0.3)

    def test_engine_downtrend(self):
        candles = downtrend_candles(120, 200, 1.0, 1000)
        ctx = self.engine.analyze("ETHUSDT", candles)
        self.assertEqual(ctx.trend, TrendDirection.BEARISH)

    def test_engine_ranging(self):
        candles = ranging_candles(120, 100, 1.0, 800)
        ctx = self.engine.analyze("SOLUSDT", candles)
        self.assertIn(ctx.regime, (MarketRegime.RANGING, MarketRegime.CALM))

    def test_engine_with_funding(self):
        candles = uptrend_candles(120, 100, 0.5, 1000)
        ctx = self.engine.analyze("BTCUSDT", candles, funding_rate=0.008)
        self.assertEqual(ctx.funding_rate, 0.008)

    def test_engine_with_spread(self):
        candles = uptrend_candles(120, 100, 0.5, 1000)
        ctx = self.engine.analyze("BTCUSDT", candles, spread=0.001)
        self.assertEqual(ctx.spread, 0.001)

    def test_engine_with_btc_dominance(self):
        candles = uptrend_candles(120, 100, 0.5, 1000)
        ctx = self.engine.analyze("BTCUSDT", candles, btc_dominance=42.5)
        self.assertEqual(ctx.btc_dominance, 42.5)

    def test_engine_multitimeframe(self):
        main = uptrend_candles(120, 100, 1.0, 1000)
        tf_h1 = uptrend_candles(80, 99, 0.8, 1200)
        tf_h4 = ranging_candles(60, 100, 3.0, 900)
        ctx = self.engine.analyze("BTCUSDT", main,
                                   timeframe_candles={"1h": tf_h1, "4h": tf_h4})
        self.assertIn("1h", ctx.timeframes)
        self.assertIn("4h", ctx.timeframes)

    def test_engine_scores_volatile_regime(self):
        candles = volatile_candles(120, 100, 5.0, 2000)
        ctx = self.engine.analyze("BTCUSDT", candles)
        self.assertIn(ctx.regime, (MarketRegime.VOLATILE, MarketRegime.REVERSAL))
        self.assertGreater(ctx.volatility_score, 0.0)

    def test_engine_institutional_score(self):
        candles = uptrend_candles(120, 100, 1.0, 2000)
        ctx = self.engine.analyze("BTCUSDT", candles,
                                   funding_rate=-0.0005, spread=0.0003,
                                   btc_correlation=0.85, eth_correlation=0.75, btc_dominance=44.0)
        self.assertGreater(ctx.institutional_score, 0.3)
        self.assertGreaterEqual(ctx.institutional_score, 0.0)
        self.assertLessEqual(ctx.institutional_score, 1.0)

    def test_engine_empty_candles_raises(self):
        with self.assertRaises(ValueError):
            self.engine.analyze("BTCUSDT", [])

    def test_engine_last_context(self):
        candles = uptrend_candles(120, 100, 1.0, 1000)
        ctx1 = self.engine.analyze("BTCUSDT", candles)
        ctx2 = self.engine.last_context()
        self.assertIsNotNone(ctx2)
        self.assertEqual(ctx1.pair, ctx2.pair)


class TestReportGeneration(unittest.TestCase):

    def test_generate_report(self):
        candles = uptrend_candles(120, 100, 1.0, 1000)
        engine = MarketEngine()
        ctx = engine.analyze("BTCUSDT", candles)
        report = generate_report(ctx)
        self.assertIn("MARKET INTELLIGENCE REPORT", report)
        self.assertIn("BTCUSDT", report)
        self.assertIn("Market Score", report)
        self.assertIn("Institutional Score", report)
        self.assertIn("TECHNICAL INDICATORS", report)

    def test_generate_summary(self):
        candles = uptrend_candles(120, 100, 1.0, 1000)
        engine = MarketEngine()
        ctx = engine.analyze("BTCUSDT", candles)
        summary = generate_summary(ctx)
        self.assertIn("BTCUSDT", summary)
        self.assertIn("Score:", summary)


class TestMarketContextExport(unittest.TestCase):

    def test_to_dict(self):
        candles = uptrend_candles(120, 100, 1.0, 1000)
        engine = MarketEngine()
        ctx = engine.analyze("BTCUSDT", candles)
        d = ctx.to_dict()
        self.assertEqual(d["pair"], "BTCUSDT")
        self.assertIn("market_score", d)
        self.assertIn("trend_score", d)
        self.assertIn("regime", d)


# ============================================================
# PERFORMANCE TEST
# ============================================================

class TestPerformance(unittest.TestCase):

    def test_engine_100_analyses(self):
        engine = MarketEngine()
        candles = uptrend_candles(200, 100, 1.0, 1000)
        start = time.time()
        for _ in range(100):
            engine.analyze("BTCUSDT", candles,
                           funding_rate=-0.0001, spread=0.0002)
        elapsed = time.time() - start
        avg = elapsed / 100
        self.assertLess(avg, 0.1, f"Average analysis time {avg:.4f}s exceeds 100ms")


# ============================================================
# STRESS TEST
# ============================================================

class TestStress(unittest.TestCase):

    def test_large_candle_input(self):
        candles = uptrend_candles(5000, 100, 0.5, 1000)
        engine = MarketEngine()
        start = time.time()
        ctx = engine.analyze("BTCUSDT", candles)
        elapsed = time.time() - start
        self.assertLess(elapsed, 2.0, f"5000 candles took {elapsed:.2f}s")
        self.assertGreater(ctx.market_score, 0)

    def test_multi_timeframe_stress(self):
        main = uptrend_candles(300, 100, 1.0, 1000)
        tfs = {f"tf_{i}": uptrend_candles(200, 100, 0.5, 1000) for i in range(10)}
        engine = MarketEngine()
        start = time.time()
        ctx = engine.analyze("BTCUSDT", main, timeframe_candles=tfs)
        elapsed = time.time() - start
        self.assertLess(elapsed, 3.0, f"10 timeframes took {elapsed:.2f}s")
        self.assertEqual(len(ctx.timeframes), 10)

    def test_edge_case_zero_volume(self):
        candles = [make_candle(100.0 + i * 0.5, volume=0.0) for i in range(100)]
        engine = MarketEngine()
        ctx = engine.analyze("BTCUSDT", candles)
        self.assertEqual(ctx.indicators.volume, 0.0)

    def test_edge_case_single_candle(self):
        candles = [make_candle(100.0)]
        engine = MarketEngine()
        ctx = engine.analyze("BTCUSDT", candles)
        self.assertAlmostEqual(ctx.price, 100.0)

    def test_edge_case_extreme_values(self):
        candles = uptrend_candles(100, 0.00001, 0.0001)
        engine = MarketEngine()
        ctx = engine.analyze("BTCUSDT", candles)
        self.assertGreater(ctx.price, 0)

    def test_edge_case_negative_spread(self):
        candles = uptrend_candles(100, 100, 1.0, 1000)
        engine = MarketEngine()
        ctx = engine.analyze("BTCUSDT", candles, spread=-0.001)
        self.assertEqual(ctx.spread, -0.001)


if __name__ == "__main__":
    unittest.main()
