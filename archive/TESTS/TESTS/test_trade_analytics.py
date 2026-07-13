import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timezone

from ENGINE.analytics.trade_analytics import TradeAnalytics, TradeRecord
from ENGINE.risk.resistance_scanner import (
    ResistanceLevel, ResistanceType, compute_validated_score,
    scan_resistance,
)
from ENGINE.scanner.scanner_config import RR_MIN_RR


class TestTradeAnalytics(unittest.TestCase):

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self.ta = TradeAnalytics(trades_dir=self._tmpdir)

    def tearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_record_entry_creates_file(self):
        rec = self.ta.record_entry(
            signal_id="test_001", symbol="BTCUSDT", direction="LONG",
            entry_price=50000, stop_loss=49500, tp1=51500,
            atr=500, adx=30, rvol=1.2,
        )
        self.assertIsNotNone(rec)
        self.assertEqual(rec.status, "OPEN")
        path = os.path.join(self._tmpdir, "test_001.json")
        self.assertTrue(os.path.exists(path))

    def test_record_exit_updates_record(self):
        self.ta.record_entry(
            signal_id="test_002", symbol="BTCUSDT", direction="LONG",
            entry_price=50000, stop_loss=49500, tp1=51500,
        )
        self.ta.record_exit(
            signal_id="test_002", exit_price=51000, exit_reason="take_profit",
            mfe=2.0, mae=0.5, max_profit_before_reversal=500,
            r_multiple=1.5, pnl_percent=2.0,
        )
        rec = self.ta.get_trade("test_002")
        self.assertIsNotNone(rec)
        self.assertEqual(rec.status, "WIN")
        self.assertEqual(rec.exit_reason, "take_profit")
        self.assertAlmostEqual(rec.mfe, 2.0)
        self.assertAlmostEqual(rec.mae, 0.5)

    def test_compute_tp_efficiency_long(self):
        eff = TradeAnalytics.compute_tp_efficiency(
            max_reached=51000, tp_proposed=51500,
            entry=50000, direction="LONG",
        )
        self.assertAlmostEqual(eff, 66.7, places=1)

    def test_compute_tp_efficiency_short(self):
        eff = TradeAnalytics.compute_tp_efficiency(
            max_reached=48000, tp_proposed=47500,
            entry=49000, direction="SHORT",
        )
        self.assertAlmostEqual(eff, 66.7, places=1)

    def test_compute_tp_efficiency_full(self):
        eff = TradeAnalytics.compute_tp_efficiency(
            max_reached=51500, tp_proposed=51500,
            entry=50000, direction="LONG",
        )
        self.assertAlmostEqual(eff, 100.0)

    def test_compute_tp_efficiency_zero_tp(self):
        eff = TradeAnalytics.compute_tp_efficiency(
            max_reached=50000, tp_proposed=0,
            entry=50000, direction="LONG",
        )
        self.assertEqual(eff, 0.0)

    def test_detect_tp_too_far_true(self):
        self.assertTrue(TradeAnalytics.detect_tp_too_far(
            max_price=51350, entry=50000, tp1=51500, direction="LONG",
        ))

    def test_detect_tp_too_far_false(self):
        self.assertFalse(TradeAnalytics.detect_tp_too_far(
            max_price=51000, entry=50000, tp1=51500, direction="LONG",
        ))

    def test_detect_tp_too_far_short(self):
        self.assertTrue(TradeAnalytics.detect_tp_too_far(
            max_price=48650, entry=50000, tp1=48500, direction="SHORT",
        ))

    def test_get_stats_empty(self):
        stats = self.ta.get_stats()
        self.assertEqual(stats.get("total_trades"), 0)

    def test_get_stats_with_trades(self):
        self.ta.record_entry(signal_id="s1", symbol="BTC", direction="LONG",
                             entry_price=50000, stop_loss=49500, tp1=51500)
        self.ta.record_entry(signal_id="s2", symbol="ETH", direction="SHORT",
                             entry_price=3000, stop_loss=3100, tp1=2800)
        self.ta.record_exit(signal_id="s1", exit_price=51500,
                            exit_reason="take_profit", mfe=3.0, mae=0.5,
                            max_profit_before_reversal=1500,
                            r_multiple=2.0, pnl_percent=3.0)
        self.ta.record_exit(signal_id="s2", exit_price=2950,
                            exit_reason="stop_loss", mfe=2.0, mae=1.0,
                            max_profit_before_reversal=100,
                            r_multiple=-1.0, pnl_percent=-1.67)
        stats = self.ta.get_stats()
        self.assertEqual(stats["total_trades"], 2)
        self.assertGreater(stats["avg_tp_efficiency"], 0)
        self.assertIn("tp_efficiency_classification", stats)

    def test_telemetry_defaults(self):
        tel = self.ta.get_telemetry()
        self.assertEqual(tel["adaptive_tp_used"], 0)
        self.assertEqual(tel["fallback_tp"], 0)

    def test_increment_telemetry(self):
        self.ta.increment_telemetry("adaptive_tp_used")
        self.ta.increment_telemetry("adaptive_tp_used")
        self.ta.increment_telemetry("fallback_tp")
        tel = self.ta.get_telemetry()
        self.assertEqual(tel["adaptive_tp_used"], 2)
        self.assertEqual(tel["fallback_tp"], 1)

    def test_learning_report_none_below_300(self):
        for i in range(20):
            sid = f"l{i}"
            self.ta.record_entry(signal_id=sid, symbol="BTC", direction="LONG",
                                 entry_price=50000, stop_loss=49500, tp1=51500)
            self.ta.record_exit(signal_id=sid, exit_price=51000,
                                exit_reason="take_profit", mfe=2.0, mae=0.5,
                                max_profit_before_reversal=1000,
                                r_multiple=1.0, pnl_percent=1.0)
        report = self.ta.generate_learning_report()
        self.assertIsNone(report)

    def test_classify_efficiency(self):
        self.assertEqual(TradeAnalytics._classify_efficiency(96), "Excelente")
        self.assertEqual(TradeAnalytics._classify_efficiency(90), "Boa")
        self.assertEqual(TradeAnalytics._classify_efficiency(75), "Media")
        self.assertEqual(TradeAnalytics._classify_efficiency(50), "Ruim")

    def test_record_exit_tp_too_far_detected(self):
        self.ta.record_entry(
            signal_id="ttf001", symbol="BTC", direction="LONG",
            entry_price=50000, stop_loss=49500, tp1=51500,
        )
        self.ta.record_exit(
            signal_id="ttf001", exit_price=49600, exit_reason="stop_loss",
            mfe=2.5, mae=0.8, max_profit_before_reversal=2.8,
        )
        rec = self.ta.get_trade("ttf001")
        self.assertTrue(rec.tp_too_far)

    def test_record_exit_tp_too_far_not_detected(self):
        self.ta.record_entry(
            signal_id="ttf002", symbol="BTC", direction="LONG",
            entry_price=50000, stop_loss=49500, tp1=51500,
        )
        self.ta.record_exit(
            signal_id="ttf002", exit_price=51200, exit_reason="take_profit",
            mfe=2.4, mae=0.3, max_profit_before_reversal=2.4,
        )
        rec = self.ta.get_trade("ttf002")
        self.assertFalse(rec.tp_too_far)

    def test_telemetry_tp_too_far_counted(self):
        self.ta.record_entry(signal_id="tc1", symbol="A", direction="LONG",
                             entry_price=100, stop_loss=95, tp1=120)
        self.ta.record_exit(signal_id="tc1", exit_price=96,
                            exit_reason="stop_loss", max_profit_before_reversal=18)
        tel = self.ta.get_telemetry()
        self.assertEqual(tel["tp_too_far"], 1)

    def test_telemetry_partial_counted(self):
        self.ta.record_entry(signal_id="pc1", symbol="A", direction="LONG",
                             entry_price=100, stop_loss=95, tp1=120)
        self.ta.record_exit(signal_id="pc1", exit_price=110,
                            exit_reason="take_profit",
                            partial_filled=True)
        tel = self.ta.get_telemetry()
        self.assertEqual(tel["partial_tp"], 1)

    def test_trade_record_dataclass(self):
        rec = TradeRecord(
            signal_id="x", symbol="X", direction="LONG",
            entry_price=10, stop_loss=9, tp1=12,
        )
        self.assertEqual(rec.symbol, "X")
        self.assertEqual(rec.status, "OPEN")


class TestResistanceScore(unittest.TestCase):

    def _ohlc(self):
        import random
        random.seed(42)
        n = 100
        base = 50000
        highs = [base + random.uniform(-200, 300) for _ in range(n)]
        lows = [base + random.uniform(-300, 200) for _ in range(n)]
        closes = [(highs[i] + lows[i]) / 2 for i in range(n)]
        highs[20] = 51000
        lows[20] = 50500
        closes[20] = 50750
        return closes, highs, lows

    def test_compute_validated_score_minimum(self):
        closes, highs, lows = self._ohlc()
        level = ResistanceLevel(
            rtype=ResistanceType.SWING_HIGH,
            price=51000, strength=0.3,
        )
        score = compute_validated_score(level, highs, lows, closes)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)

    def test_validated_score_order_block_bonus(self):
        level = ResistanceLevel(
            rtype=ResistanceType.ORDER_BLOCK,
            price=50000, strength=0.5,
        )
        score = compute_validated_score(level, [50000], [49000], [49500])
        self.assertGreater(score, 15)

    def test_score_added_to_scan_result(self):
        closes, highs, lows = self._ohlc()
        levels = scan_resistance(highs, lows, closes)
        for lv in levels:
            self.assertGreaterEqual(lv.validated_score, 0)
            self.assertLessEqual(lv.validated_score, 100)

    def test_strong_level_has_higher_score(self):
        weak = ResistanceLevel(
            rtype=ResistanceType.FVG,
            price=50000, strength=0.2,
        )
        strong = ResistanceLevel(
            rtype=ResistanceType.ORDER_BLOCK,
            price=50000, strength=0.9,
        )
        score_w = compute_validated_score(weak, [50000], [49000], [49500])
        score_s = compute_validated_score(strong, [50000], [49000], [49500])
        self.assertGreater(score_s, score_w)


class TestSafetyRR(unittest.TestCase):

    def test_rr_min_constant_exists(self):
        self.assertEqual(RR_MIN_RR, 2.0)

    def test_adaptive_tp_enforces_rr_min(self):
        from ENGINE.risk.tp_adaptativo import calculate_adaptive_tp
        result = calculate_adaptive_tp(
            entry=50000, stop_loss=49500, direction="LONG",
            atr=200, closes=[50000]*100, highs=[50200]*100, lows=[49800]*100,
        )
        self.assertGreaterEqual(
            (result.tp1 - 50000) / (50000 - 49500),
            2.0,
        )

    def test_adaptive_tp_allows_rr_above_min(self):
        from ENGINE.risk.tp_adaptativo import calculate_adaptive_tp
        result = calculate_adaptive_tp(
            entry=50000, stop_loss=48000, direction="LONG",
            atr=500, closes=[50000]*100, highs=[52000]*100, lows=[48000]*100,
        )
        self.assertGreaterEqual((result.tp1 - 50000) / (50000 - 48000), 2.0)

    def test_adaptive_tp_rr_short(self):
        from ENGINE.risk.tp_adaptativo import calculate_adaptive_tp
        result = calculate_adaptive_tp(
            entry=50000, stop_loss=50500, direction="SHORT",
            atr=200, closes=[50000]*100, highs=[50200]*100, lows=[49800]*100,
        )
        self.assertGreaterEqual(
            (50000 - result.tp1) / (50500 - 50000),
            2.0,
        )


class TestPaperTradeV191(unittest.TestCase):

    def setUp(self):
        from CORE.trading.paper_trading import PaperTradingEngine
        self._tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self._tmpdir, "paper.json")
        self.engine = PaperTradingEngine(db_path=self.db_path)

    def tearDown(self):
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_tracks_highest_and_lowest_seen(self):
        self.engine.record_entry(
            pair="BTCUSDT", direction="LONG",
            entry_price=50000, stop_loss=49500, take_profit=51500,
            cycle=1, quality=0.75,
        )
        self.engine.check_exits({"BTCUSDT": 50500})
        self.engine.check_exits({"BTCUSDT": 51000})
        self.engine.check_exits({"BTCUSDT": 50700})
        trades = list(self.engine._open_trades.values())
        self.assertEqual(trades[0].highest_seen, 51000)
        self.assertEqual(trades[0].lowest_seen, 50000)

    def test_max_profit_before_reversal_tracked(self):
        self.engine.record_entry(
            pair="BTCUSDT", direction="LONG",
            entry_price=50000, stop_loss=49500, take_profit=51500,
            cycle=1, quality=0.75,
        )
        self.engine.check_exits({"BTCUSDT": 51000})
        self.engine.check_exits({"BTCUSDT": 50500})
        trades = list(self.engine._open_trades.values())
        self.assertGreater(trades[0].max_profit_before_reversal, 0)

    def test_exit_reason_stored(self):
        self.engine.record_entry(
            pair="BTCUSDT", direction="LONG",
            entry_price=50000, stop_loss=49500, take_profit=51500,
            cycle=1, quality=0.75,
        )
        closed = self.engine.check_exits({"BTCUSDT": 49400})
        self.assertEqual(len(closed), 1)
        self.assertEqual(closed[0].exit_reason, "stop_loss")

    def test_exit_reason_take_profit(self):
        self.engine.record_entry(
            pair="BTCUSDT", direction="LONG",
            entry_price=50000, stop_loss=49500, take_profit=51000,
            cycle=1, quality=0.75,
        )
        closed = self.engine.check_exits({"BTCUSDT": 51000})
        self.assertEqual(len(closed), 1)
        self.assertIn(closed[0].exit_reason, ("take_profit",))

    def test_short_tracks_lowest_as_mfe(self):
        self.engine.record_entry(
            pair="BTCUSDT", direction="SHORT",
            entry_price=50000, stop_loss=50500, take_profit=48500,
            cycle=1, quality=0.75,
        )
        self.engine.check_exits({"BTCUSDT": 49000})
        self.engine.check_exits({"BTCUSDT": 49500})
        trades = list(self.engine._open_trades.values())
        self.assertEqual(trades[0].lowest_seen, 49000)

    def test_short_exit_reason_stored(self):
        self.engine.record_entry(
            pair="BTCUSDT", direction="SHORT",
            entry_price=50000, stop_loss=50500, take_profit=48500,
            cycle=1, quality=0.75,
        )
        closed = self.engine.check_exits({"BTCUSDT": 50600})
        self.assertEqual(len(closed), 1)
        self.assertEqual(closed[0].exit_reason, "stop_loss")

    def test_get_stats_tp_efficiency(self):
        self.engine.record_entry(
            pair="BTCUSDT", direction="LONG",
            entry_price=50000, stop_loss=49500, take_profit=51000,
            cycle=1, quality=0.75,
        )
        closed = self.engine.check_exits({"BTCUSDT": 51000})
        self.assertEqual(len(closed), 1)
        stats = self.engine.get_stats()
        self.assertIn("avg_tp_efficiency", stats)

    def test_get_stats_partial_pct(self):
        self.engine.record_entry(
            pair="BTCUSDT", direction="LONG",
            entry_price=50000, stop_loss=49500, take_profit=51500,
            cycle=1, quality=0.75, partial_tp=50500, take_profit_2=52500,
        )
        self.engine.check_exits({"BTCUSDT": 50500})
        closed = self.engine.check_exits({"BTCUSDT": 49400})
        self.assertEqual(len(closed), 1)
        stats = self.engine.get_stats()
        self.assertIn("partial_tp_pct", stats)
