import unittest
from typing import List


class TestResistanceScanner(unittest.TestCase):

    def setUp(self):
        from ENGINE.risk.resistance_scanner import (
            scan_resistance, find_nearest_resistance_above,
            find_nearest_resistance_below, ResistanceType,
        )
        self.scan_resistance = scan_resistance
        self.find_above = find_nearest_resistance_above
        self.find_below = find_nearest_resistance_below
        self.ResistanceType = ResistanceType

    def _ohlc(self, prices: List[float]):
        highs = [p * 1.005 for p in prices]
        lows = [p * 0.995 for p in prices]
        return highs, lows, prices[:]

    def test_scan_swing_highs(self):
        prices = [100, 103, 108, 104, 101, 102, 107, 103, 100, 101,
                  105, 102, 99, 98, 101, 106, 103, 100, 102, 110,
                  107, 104, 101, 103, 108, 105, 102, 100, 103, 106]
        highs, lows, closes = self._ohlc(prices)
        levels = self.scan_resistance(highs, lows, closes)
        swing = [l for l in levels if l.rtype == self.ResistanceType.SWING_HIGH]
        self.assertTrue(len(swing) >= 1)

    def test_nearest_resistance_above(self):
        prices = [100, 102, 105, 103, 101]
        highs, lows, closes = self._ohlc(prices)
        levels = self.scan_resistance(highs, lows, closes)
        nearest = self.find_above(101, levels)
        self.assertIsNotNone(nearest)
        self.assertGreater(nearest.price, 101)

    def test_nearest_resistance_below(self):
        prices = [100, 102, 105, 103, 101]
        highs, lows, closes = self._ohlc(prices)
        levels = self.scan_resistance(highs, lows, closes)
        nearest = self.find_below(104, levels)
        self.assertIsNotNone(nearest)
        self.assertLess(nearest.price, 104)


class TestTPAdaptativo(unittest.TestCase):

    def setUp(self):
        from ENGINE.risk.tp_adaptativo import (
            calculate_adaptive_tp, calculate_tp_probability,
            calculate_target_difficulty, should_take_partial,
            should_activate_trailing, calculate_trailing_stop,
        )
        self.calc_tp = calculate_adaptive_tp
        self.calc_prob = calculate_tp_probability
        self.calc_diff = calculate_target_difficulty
        self.should_partial = should_take_partial
        self.should_trail = should_activate_trailing
        self.calc_trail = calculate_trailing_stop

    def _ohlc(self, n=50, base=50000):
        import math
        closes = [base + math.sin(i * 0.3) * 200 + i * 5 for i in range(n)]
        highs = [c * 1.01 for c in closes]
        lows = [c * 0.99 for c in closes]
        return closes, highs, lows

    def test_calculate_adaptive_tp_long(self):
        closes, highs, lows = self._ohlc()
        result = self.calc_tp(
            entry=50000, stop_loss=49500, direction="LONG",
            atr=500, closes=closes, highs=highs, lows=lows,
        )
        self.assertGreater(result.tp1, 50000)
        self.assertGreater(result.tp2, result.tp1)
        self.assertGreater(result.partial_tp, 0)
        self.assertGreater(result.tp_probability, 0)

    def test_calculate_adaptive_tp_short(self):
        closes, highs, lows = self._ohlc()
        result = self.calc_tp(
            entry=50000, stop_loss=50500, direction="SHORT",
            atr=500, closes=closes, highs=highs, lows=lows,
        )
        self.assertLess(result.tp1, 50000)
        self.assertLess(result.tp2, result.tp1)
        self.assertLess(result.partial_tp, 50000)

    def test_tp_probability_high(self):
        prob = self.calc_prob(
            trend_score=0.9, momentum=0.8, adx=40,
            volume_ratio=1.5, distance_to_resistance_pct=0.05,
        )
        self.assertGreaterEqual(prob, 0)
        self.assertLessEqual(prob, 100)

    def test_tp_probability_low(self):
        prob = self.calc_prob(
            trend_score=0.2, momentum=0.2, adx=15,
            volume_ratio=0.5, distance_to_resistance_pct=0.5,
        )
        self.assertGreaterEqual(prob, 0)

    def test_target_difficulty(self):
        diff = self.calc_diff(atr_pct=0.02, distance_to_resistance_pct=0.03)
        self.assertGreaterEqual(diff, 0)
        self.assertLessEqual(diff, 100)

    def test_should_take_partial_long(self):
        result, reason = self.should_partial(
            current_price=51000, entry_price=50000,
            direction="LONG", atr=500, partial_tp=50900,
        )
        self.assertTrue(result)
        self.assertIn("partial", reason)

    def test_should_not_take_partial_long(self):
        result, reason = self.should_partial(
            current_price=50100, entry_price=50000,
            direction="LONG", atr=500, partial_tp=50900,
        )
        self.assertFalse(result)

    def test_should_activate_trailing_long(self):
        act = self.should_trail(
            current_price=51000, entry_price=50000,
            direction="LONG", tp1=50800,
        )
        self.assertTrue(act)

    def test_should_not_activate_trailing_long(self):
        act = self.should_trail(
            current_price=50500, entry_price=50000,
            direction="LONG", tp1=50800,
        )
        self.assertFalse(act)

    def test_calculate_trailing_stop_long(self):
        closes = [50000 + i * 10 for i in range(30)]
        ts = self.calc_trail(
            current_price=51000, entry_price=50000,
            direction="LONG", atr=500, closes=closes,
        )
        self.assertIsNotNone(ts)
        self.assertGreaterEqual(ts, 50000)
        self.assertLess(ts, 51000)

    def test_calculate_trailing_stop_short(self):
        closes = [50000 - i * 10 for i in range(30)]
        ts = self.calc_trail(
            current_price=49000, entry_price=50000,
            direction="SHORT", atr=500, closes=closes,
        )
        self.assertIsNotNone(ts)
        self.assertLessEqual(ts, 50000)
        self.assertGreater(ts, 49000)

    def test_tp_low_probability_reduces_tp(self):
        closes, highs, lows = self._ohlc()
        result = self.calc_tp(
            entry=50000, stop_loss=49620, direction="LONG",
            atr=500, closes=closes, highs=highs, lows=lows,
            trend_score=0.1, momentum=0.1, adx=10,
        )
        self.assertLess(result.tp_probability, 80)
        standard_tp = 50000 + 500 * 1.8
        self.assertLess(result.tp1, standard_tp)

    def test_difficulty_high_reduces_tp(self):
        closes, highs, lows = self._ohlc()
        result = self.calc_tp(
            entry=50000, stop_loss=49500, direction="LONG",
            atr=2000, closes=closes, highs=highs, lows=lows,
        )
        standard_tp = 50000 + 2000 * 1.8
        self.assertLess(result.tp1, standard_tp)


class TestPaperTradeV19(unittest.TestCase):

    def setUp(self):
        from CORE.trading.paper_trading import PaperTradingEngine, PaperTrade
        self.PaperTrade = PaperTrade
        import tempfile
        self.tmp_db = tempfile.mktemp(suffix=".json")
        self.engine = PaperTradingEngine(db_path=self.tmp_db)

    def tearDown(self):
        import os
        try:
            os.unlink(self.tmp_db)
        except Exception:
            pass

    def test_record_entry_with_v19_fields(self):
        import json
        trade = self.engine.record_entry(
            pair="BTCUSDT", direction="LONG",
            entry_price=50000, stop_loss=49500, take_profit=51500,
            cycle=1, quality=0.75,
            take_profit_2=52500, partial_tp=50900, break_even_price=50000,
        )
        self.assertIsNotNone(trade)
        self.assertEqual(trade.take_profit_2, 52500)
        self.assertEqual(trade.partial_tp, 50900)
        self.assertEqual(trade.break_even_price, 50000)
        self.assertFalse(trade.partial_filled)
        self.assertFalse(trade.trailing_active)

    def test_partial_then_stop_at_be(self):
        self.engine.record_entry(
            pair="BTCUSDT", direction="LONG",
            entry_price=50000, stop_loss=49500, take_profit=52000,
            cycle=1, quality=0.75,
            take_profit_2=53000, partial_tp=50900, break_even_price=50000,
        )
        trades = self.engine.check_exits({"BTCUSDT": 51000})
        self.assertEqual(len(trades), 0)
        self.assertEqual(len(self.engine._open_trades), 1)
        t = list(self.engine._open_trades.values())[0]
        self.assertTrue(t.partial_filled)
        self.assertEqual(t.remaining_value, t.position_value * 0.5)

    def test_tp1_activates_trailing(self):
        self.engine.record_entry(
            pair="BTCUSDT", direction="LONG",
            entry_price=50000, stop_loss=49500, take_profit=51500,
            cycle=1, quality=0.75,
            take_profit_2=53000,
        )
        trades = self.engine.check_exits({"BTCUSDT": 51600})
        self.assertEqual(len(trades), 0)
        t = list(self.engine._open_trades.values())[0]
        self.assertTrue(t.trailing_active)
        self.assertIsNotNone(t.trailing_stop_level)

    def test_tp1_closes_when_no_tp2(self):
        self.engine.record_entry(
            pair="BTCUSDT", direction="LONG",
            entry_price=50000, stop_loss=49500, take_profit=51500,
            cycle=1, quality=0.75,
        )
        trades = self.engine.check_exits({"BTCUSDT": 51500})
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].status, "WIN")

    def test_tp2_closes_trade(self):
        self.engine.record_entry(
            pair="BTCUSDT", direction="LONG",
            entry_price=50000, stop_loss=49500, take_profit=51500,
            cycle=1, quality=0.75,
            take_profit_2=53000,
        )
        trades = self.engine.check_exits({"BTCUSDT": 53000})
        self.assertEqual(len(trades), 1)

    def test_stop_loss_closes(self):
        self.engine.record_entry(
            pair="BTCUSDT", direction="LONG",
            entry_price=50000, stop_loss=49500, take_profit=51500,
            cycle=1, quality=0.75,
        )
        trades = self.engine.check_exits({"BTCUSDT": 49400})
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].status, "LOSS")


if __name__ == '__main__':
    unittest.main()
