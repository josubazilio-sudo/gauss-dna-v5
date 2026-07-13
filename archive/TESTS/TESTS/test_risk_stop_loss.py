"""
Testes de validacao de Stop Loss.

FASE 6 — Garantir que nenhum Signal saia com stop_loss=0.
"""
import unittest
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime

from ENGINE.scanner.scanner_types import (
    SignalDirection, Signal, ScannerScore, SignalClassification,
    Pattern, PatternType, MarketStructure, StructureType,
    SwingPoint, EntryZone, EntryDetails,
)
from ENGINE.risk.risk_manager import (
    calculate_stop_loss, calculate_take_profits, calculate_risk_reward,
    true_atr, _price_precision, apply,
)
from ENGINE.scanner.scanner_config import (
    RR_BASE_SL_MULTIPLIER, RR_BASE_TP1_MULTIPLIER, RR_BASE_TP2_MULTIPLIER,
    RR_MIN_RR,
)


def _make_structure(
    structure_type: StructureType = StructureType.RANGING,
    swing_lows: Optional[List[float]] = None,
    swing_highs: Optional[List[float]] = None,
    strength: float = 0.5,
) -> MarketStructure:
    lows = []
    if swing_lows:
        for i, p in enumerate(swing_lows):
            lows.append(SwingPoint(
                price=p, index=i, high=False,
            ))
    highs = []
    if swing_highs:
        for i, p in enumerate(swing_highs):
            highs.append(SwingPoint(
                price=p, index=i, high=True,
            ))
    return MarketStructure(
        structure_type=structure_type,
        structure_strength=strength,
        swing_lows=lows,
        swing_highs=highs,
        mm50=0, mm200=0, vwap=0,
    )


def _make_pattern(
    ptype: PatternType,
    direction: SignalDirection = SignalDirection.LONG,
    price: float = 50000.0,
    confidence: float = 0.8,
    strength: float = 0.7,
    lower: float = 0,
    upper: float = 0,
) -> Pattern:
    meta = {"lower": lower, "upper": upper, "index": 5} if lower or upper else {"index": 5}
    return Pattern(
        type=ptype,
        direction=direction,
        timeframe="1h",
        price=price,
        confidence=confidence,
        strength=strength,
        description="",
        metadata=meta,
    )


class TestPricePrecision(unittest.TestCase):

    def test_precision_high_price(self):
        self.assertGreaterEqual(_price_precision(50000.0), 2)
        self.assertLessEqual(_price_precision(50000.0), 6)

    def test_precision_medium_price(self):
        self.assertGreaterEqual(_price_precision(100.0), 2)

    def test_precision_low_price(self):
        prec = _price_precision(0.00002500)
        self.assertGreaterEqual(prec, 6, f"SHIB-level price needs >=6 decimals, got {prec}")

    def test_precision_very_low_price(self):
        prec = _price_precision(0.00000700)
        self.assertGreaterEqual(prec, 7, f"PEPE-level price needs >=7 decimals, got {prec}")

    def test_precision_zero_price(self):
        self.assertEqual(_price_precision(0), 8)

    def test_precision_negative_price(self):
        self.assertEqual(_price_precision(-1), 8)


class TestCalculateStopLoss(unittest.TestCase):

    def test_long_normal_price(self):
        sl = calculate_stop_loss(
            entry=50000.0, direction=SignalDirection.LONG,
            atr=800.0, structure=_make_structure(), patterns=[],
        )
        self.assertGreater(sl, 0)
        self.assertLess(sl, 50000.0)

    def test_short_normal_price(self):
        sl = calculate_stop_loss(
            entry=50000.0, direction=SignalDirection.SHORT,
            atr=800.0, structure=_make_structure(), patterns=[],
        )
        self.assertGreater(sl, 50000.0)

    def test_long_small_price_shib(self):
        """SHIB-level: ~0.00002500 USDT"""
        sl = calculate_stop_loss(
            entry=0.00002500, direction=SignalDirection.LONG,
            atr=0.000008, structure=_make_structure(), patterns=[],
        )
        self.assertGreater(sl, 0, f"SHIB LONG stop loss deve ser > 0, got {sl:.10f}")
        self.assertLess(sl, 0.00002500)

    def test_short_small_price_shib(self):
        sl = calculate_stop_loss(
            entry=0.00002500, direction=SignalDirection.SHORT,
            atr=0.000008, structure=_make_structure(), patterns=[],
        )
        self.assertGreater(sl, 0.00002500)

    def test_long_tiny_price_pepe(self):
        """PEPE-level: ~0.00000700 USDT"""
        sl = calculate_stop_loss(
            entry=0.00000700, direction=SignalDirection.LONG,
            atr=0.000003, structure=_make_structure(), patterns=[],
        )
        self.assertGreater(sl, 0, f"PEPE LONG stop loss deve ser > 0, got {sl:.10f}")
        self.assertLess(sl, 0.00000700)

    def test_atr_zero_raises(self):
        with self.assertRaises(ValueError) as ctx:
            calculate_stop_loss(
                entry=50000.0, direction=SignalDirection.LONG,
                atr=0.0, structure=_make_structure(), patterns=[],
            )
        self.assertIn("ATR", str(ctx.exception))

    def test_with_swing_low_long(self):
        swing = [49800.0]
        sl = calculate_stop_loss(
            entry=50000.0, direction=SignalDirection.LONG,
            atr=800.0, structure=_make_structure(swing_lows=swing), patterns=[],
        )
        self.assertGreater(sl, 0)
        self.assertGreaterEqual(sl, 49800.0)

    def test_with_swing_high_short(self):
        swing = [50200.0]
        sl = calculate_stop_loss(
            entry=50000.0, direction=SignalDirection.SHORT,
            atr=800.0, structure=_make_structure(swing_highs=swing), patterns=[],
        )
        self.assertGreater(sl, 50000.0)
        self.assertLessEqual(sl, 50200.0)

    def test_with_order_block_long(self):
        ob_pattern = _make_pattern(
            PatternType.ORDER_BLOCK, SignalDirection.LONG,
            price=49900.0, lower=49800.0, upper=50000.0,
        )
        sl = calculate_stop_loss(
            entry=50000.0, direction=SignalDirection.LONG,
            atr=800.0, structure=_make_structure(),
            patterns=[ob_pattern],
        )
        self.assertGreater(sl, 0)

    def test_small_atr_large_entry(self):
        sl = calculate_stop_loss(
            entry=50000.0, direction=SignalDirection.LONG,
            atr=50000.0, structure=_make_structure(), patterns=[],
        )
        self.assertGreater(sl, 0)
        self.assertLess(sl, 50000.0)

    def test_ranging_market_long(self):
        sl = calculate_stop_loss(
            entry=50000.0, direction=SignalDirection.LONG,
            atr=500.0, structure=_make_structure(StructureType.RANGING), patterns=[],
        )
        self.assertGreater(sl, 0)
        self.assertLess(sl, 50000.0)

    def test_trending_market_long(self):
        sl = calculate_stop_loss(
            entry=50000.0, direction=SignalDirection.LONG,
            atr=500.0, structure=_make_structure(StructureType.UPTREND, swing_lows=[49700]), patterns=[],
        )
        self.assertGreater(sl, 0)
        self.assertLess(sl, 50000.0)


class TestCalculateTakeProfits(unittest.TestCase):

    def test_long_normal(self):
        tp1, tp2 = calculate_take_profits(
            entry=50000.0, stop_loss=49700.0,
            direction=SignalDirection.LONG, atr=800.0,
        )
        self.assertGreater(tp1, 50000.0)
        self.assertGreater(tp2, tp1)

    def test_short_normal(self):
        tp1, tp2 = calculate_take_profits(
            entry=50000.0, stop_loss=50300.0,
            direction=SignalDirection.SHORT, atr=800.0,
        )
        self.assertLess(tp1, 50000.0)
        self.assertLess(tp2, tp1)

    def test_small_price_long(self):
        """SHIB-level: stop_loss=0, fallback = atr * RR_BASE_SL_MULTIPLIER"""
        tp1, tp2 = calculate_take_profits(
            entry=0.00002500, stop_loss=0.00002300,
            direction=SignalDirection.LONG, atr=0.000008,
        )
        self.assertGreater(tp1, 0, f"TP1 deve ser > 0, got {tp1:.10f}")
        self.assertGreater(tp2, tp1)

    def test_small_price_short(self):
        tp1, tp2 = calculate_take_profits(
            entry=0.00002500, stop_loss=0.00002700,
            direction=SignalDirection.SHORT, atr=0.000008,
        )
        self.assertGreater(tp1, 0, f"TP1 deve ser > 0, got {tp1:.10f}")
        self.assertLess(tp1, 0.00002500)
        self.assertLess(tp2, tp1)

    def test_stop_loss_zero_fallback(self):
        """Quando stop_loss=0, usa atr * mult como fallback — TP deve ser > 0"""
        tp1, tp2 = calculate_take_profits(
            entry=50000.0, stop_loss=0.0,
            direction=SignalDirection.LONG, atr=800.0,
        )
        self.assertGreater(tp1, 50000.0)
        self.assertGreater(tp2, tp1)


class TestCalculateRiskReward(unittest.TestCase):

    def test_long_valid(self):
        rr = calculate_risk_reward(
            entry=50000.0, stop_loss=49700.0,
            take_profit=50600.0, direction=SignalDirection.LONG,
        )
        self.assertGreater(rr, 0)

    def test_short_valid(self):
        rr = calculate_risk_reward(
            entry=50000.0, stop_loss=50300.0,
            take_profit=49400.0, direction=SignalDirection.SHORT,
        )
        self.assertGreater(rr, 0)

    def test_stop_equal_entry_returns_zero(self):
        rr = calculate_risk_reward(
            entry=50000.0, stop_loss=50000.0,
            take_profit=50600.0, direction=SignalDirection.LONG,
        )
        self.assertEqual(rr, 0.0)

    def test_stop_zero_long(self):
        rr = calculate_risk_reward(
            entry=50000.0, stop_loss=0.0,
            take_profit=50600.0, direction=SignalDirection.LONG,
        )
        self.assertAlmostEqual(rr, 0.01, places=4)

    def test_small_price_long(self):
        rr = calculate_risk_reward(
            entry=0.00002500, stop_loss=0.00002300,
            take_profit=0.00002900, direction=SignalDirection.LONG,
        )
        self.assertGreater(rr, 0)


class TestTrueATR(unittest.TestCase):

    def test_atr_calculation(self):
        highs = [50000, 50100, 50200, 50300, 50400, 50500, 50600, 50700, 50800, 50900,
                 51000, 51100, 51200, 51300, 51400]
        lows = [49900, 50000, 50100, 50200, 50300, 50400, 50500, 50600, 50700, 50800,
                50900, 51000, 51100, 51200, 51300]
        closes = [49950, 50050, 50150, 50250, 50350, 50450, 50550, 50650, 50750, 50850,
                  50950, 51050, 51150, 51250, 51350]
        atr = true_atr(highs, lows, closes)
        self.assertGreater(atr, 0)

    def test_atr_insufficient_data(self):
        atr = true_atr([50000], [49900], [49950])
        self.assertEqual(atr, 0.0)


class TestApplyRiskManager(unittest.TestCase):

    def setUp(self):
        self.signal = Signal(
            ticker="SHIBUSDT",
            timeframe="1h",
            direction=SignalDirection.LONG,
            entry_price=0.00002500,
            stop_loss=0.0,
            take_profit_1=0.0,
            take_profit_2=0.0,
            risk_reward=0.0,
            scores=ScannerScore(),
            classification=SignalClassification.PRATA,
            patterns=[],
            structure=_make_structure(StructureType.RANGING),
            rvol=1.5,
            adx=30,
            atr_value=0.000008,
            regime="uptrend",
            setup="",
            context="",
            approval_reasons=[],
            rejection_reasons=[],
            confidence=0.8,
            quality=0.8,
        )

    def test_apply_long_normal(self):
        self.signal.entry_price = 50000.0
        self.signal.atr_value = 800.0
        self.signal.ticker = "BTCUSDT"
        result = apply(
            signal=self.signal,
            direction=SignalDirection.LONG,
            atr=self.signal.atr_value,
            structure=self.signal.structure,
            patterns=self.signal.patterns,
        )
        self.assertGreater(result.stop_loss, 0)
        self.assertGreater(result.take_profit_1, 0)
        self.assertGreater(result.entry_price, 0)

    def test_apply_shib_long(self):
        """SHIB-level: stop_loss > 0 apos correcao do round(sl, 4)"""
        result = apply(
            signal=self.signal,
            direction=SignalDirection.LONG,
            atr=self.signal.atr_value,
            structure=self.signal.structure,
            patterns=self.signal.patterns,
        )
        self.assertGreater(result.stop_loss, 0,
                           f"SHIB stop loss deve ser > 0, got {result.stop_loss:.10f}")
        self.assertGreater(result.take_profit_1, 0)
        self.assertGreater(result.entry_price, 0)
        self.assertGreaterEqual(result.risk_reward, 0)

    def test_apply_short_shib(self):
        self.signal.direction = SignalDirection.SHORT
        self.signal.ticker = "SHIBUSDT"
        result = apply(
            signal=self.signal,
            direction=SignalDirection.SHORT,
            atr=self.signal.atr_value,
            structure=self.signal.structure,
            patterns=self.signal.patterns,
        )
        self.assertGreater(result.stop_loss, 0,
                           f"SHIB SHORT stop loss deve ser > 0, got {result.stop_loss:.10f}")
        self.assertGreater(result.take_profit_1, 0)
        self.assertGreater(result.entry_price, 0)

    def test_apply_atr_zero_raises(self):
        self.signal.atr_value = 0.0
        self.signal.ticker = "BTCUSDT"
        self.signal.entry_price = 50000.0
        with self.assertRaises(ValueError):
            apply(
                signal=self.signal,
                direction=SignalDirection.LONG,
                atr=0.0,
                structure=self.signal.structure,
                patterns=self.signal.patterns,
            )

    def test_apply_low_liquidity(self):
        self.signal.atr_value = 0.000001
        self.signal.entry_price = 0.00002500
        result = apply(
            signal=self.signal,
            direction=SignalDirection.LONG,
            atr=self.signal.atr_value,
            structure=self.signal.structure,
            patterns=self.signal.patterns,
        )
        self.assertGreater(result.stop_loss, 0)
        self.assertGreater(result.entry_price, 0)

    def test_apply_large_atr_gap(self):
        """ATR grande em relacao ao preco — stop capped at 5%"""
        self.signal.entry_price = 0.00002500
        self.signal.atr_value = 0.000050
        result = apply(
            signal=self.signal,
            direction=SignalDirection.LONG,
            atr=self.signal.atr_value,
            structure=self.signal.structure,
            patterns=self.signal.patterns,
        )
        self.assertGreater(result.stop_loss, 0)
        self.assertGreater(result.entry_price, 0)


if __name__ == '__main__':
    unittest.main()
