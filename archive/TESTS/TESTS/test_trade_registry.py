import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone


class TestTradeRegistry(unittest.TestCase):

    def setUp(self):
        self.tmp_db = tempfile.mktemp(suffix=".db")
        from ENGINE.common.trade_registry import TradeRegistry
        self.registry = TradeRegistry(db_path=self.tmp_db)

    def tearDown(self):
        try:
            os.unlink(self.tmp_db)
        except Exception:
            pass

    def _signal_data(self, **overrides):
        data = {
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "direction": "LONG",
            "entry_price": 50000.0,
            "stop_loss": 49500.0,
            "take_profit_1": 51000.0,
            "take_profit_2": 52000.0,
            "quality_score": 0.75,
            "confidence_score": 0.82,
            "overall_score_value": 82.5,
            "consensus_score": 0.78,
            "conviction_level": "Alta",
            "expectancy_level": "Moderada",
            "trend": "uptrend",
            "kalman_direction": "UP",
            "classification_label": "GOLD",
            "risk_reward": 2.0,
            "cycle_id": 42,
            "signal_id": "SIG-TEST-001",
        }
        data.update(overrides)
        return data

    def test_open_trade(self):
        trade_id = self.registry.open_trade(self._signal_data())
        self.assertIsNotNone(trade_id)
        self.assertTrue(len(trade_id) > 0)

        trades = self.registry.get_open_trades()
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]["asset"], "BTCUSDT")

    def test_close_trade(self):
        self.registry.open_trade(self._signal_data())
        ok = self.registry.close_trade(
            signal_id="SIG-TEST-001",
            resultado="WIN",
            exit_price=51000.0,
            lucro_usdt=50.0,
            perda_usdt=0.0,
            retorno_pct=2.0,
            r_multiple=2.0,
        )
        self.assertTrue(ok)

        trade = self.registry.get_trade_by_signal_id("SIG-TEST-001")
        self.assertIsNotNone(trade)
        self.assertEqual(trade["resultado"], "WIN")

    def test_close_trade_no_open(self):
        ok = self.registry.close_trade(signal_id="NONEXISTENT", resultado="WIN")
        self.assertFalse(ok)

    def test_statistics_empty(self):
        stats = self.registry.get_statistics()
        self.assertEqual(stats.get("total_trades"), 0)
        self.assertEqual(stats.get("status"), "no_trades")

    def test_statistics_with_trades(self):
        self.registry.open_trade(self._signal_data(signal_id="SIG-001"))
        self.registry.close_trade("SIG-001", "WIN", lucro_usdt=50, perda_usdt=0, retorno_pct=2.0)

        self.registry.open_trade(self._signal_data(signal_id="SIG-002", symbol="ETHUSDT"))
        self.registry.close_trade("SIG-002", "LOSS", lucro_usdt=0, perda_usdt=30, retorno_pct=-1.5)

        stats = self.registry.get_statistics()
        self.assertEqual(stats["total_trades"], 2)
        self.assertEqual(stats["winning_trades"], 1)
        self.assertEqual(stats["losing_trades"], 1)
        self.assertEqual(stats["win_rate"], 50.0)

    def test_statistics_by_classification(self):
        self.registry.open_trade(self._signal_data(signal_id="SIG-01", classification_label="GOLD", overall_score_value=85))
        self.registry.close_trade("SIG-01", "WIN", lucro_usdt=50, retorno_pct=2.0)

        self.registry.open_trade(self._signal_data(signal_id="SIG-02", classification_label="SILVER", overall_score_value=78))
        self.registry.close_trade("SIG-02", "LOSS", perda_usdt=20, retorno_pct=-1.0)

        by_cls = self.registry.get_statistics_by_classification()
        self.assertIn("GOLD", by_cls)
        self.assertIn("SILVER", by_cls)
        self.assertEqual(by_cls["GOLD"]["wins"], 1)
        self.assertEqual(by_cls["SILVER"]["losses"], 1)

    def test_statistics_by_timeframe(self):
        self.registry.open_trade(self._signal_data(signal_id="SIG-TF1", timeframe="1h"))
        self.registry.close_trade("SIG-TF1", "WIN", lucro_usdt=30)

        self.registry.open_trade(self._signal_data(signal_id="SIG-TF2", timeframe="4h"))
        self.registry.close_trade("SIG-TF2", "LOSS", perda_usdt=10)

        by_tf = self.registry.get_statistics_by_timeframe()
        self.assertIn("1h", by_tf)
        self.assertIn("4h", by_tf)

    def test_statistics_by_direction(self):
        self.registry.open_trade(self._signal_data(signal_id="SIG-D1", direction="LONG"))
        self.registry.close_trade("SIG-D1", "WIN", lucro_usdt=40)

        self.registry.open_trade(self._signal_data(signal_id="SIG-D2", direction="SHORT"))
        self.registry.close_trade("SIG-D2", "LOSS", perda_usdt=15)

        by_dir = self.registry.get_statistics_by_direction()
        self.assertIn("LONG", by_dir)
        self.assertIn("SHORT", by_dir)
        self.assertEqual(by_dir["LONG"]["wins"], 1)

    def test_setup_ranking(self):
        self.registry.open_trade(self._signal_data(signal_id="SIG-S1", trend="uptrend", kalman_direction="UP"))
        self.registry.close_trade("SIG-S1", "WIN", lucro_usdt=50)

        self.registry.open_trade(self._signal_data(signal_id="SIG-S2", trend="uptrend", kalman_direction="UP"))
        self.registry.close_trade("SIG-S2", "WIN", lucro_usdt=30)

        self.registry.open_trade(self._signal_data(signal_id="SIG-S3", trend="downtrend", kalman_direction="DOWN"))
        self.registry.close_trade("SIG-S3", "LOSS", perda_usdt=20)

        setups = self.registry.get_setup_ranking(min_trades=1)
        self.assertTrue(len(setups) >= 2)
        trend_up = [s for s in setups if "UPTREND" in s["setup"] and "UP" in s["setup"]]
        self.assertTrue(len(trend_up) > 0)
        self.assertEqual(trend_up[0]["wins"], 2)

    def test_loss_analysis(self):
        self.registry.open_trade(self._signal_data(
            signal_id="SIG-L1", quality_score=0.65, confidence_score=0.70,
            consensus_score=0.60, risk_reward=1.5, overall_score_value=62,
        ))
        self.registry.close_trade("SIG-L1", "LOSS", perda_usdt=25, retorno_pct=-2.0)

        loss = self.registry.get_loss_analysis()
        self.assertEqual(loss["total_losses"], 1)
        self.assertTrue(len(loss["weak_gate_ranking"]) > 0)

    def test_weekly_report_empty(self):
        report = self.registry.get_weekly_report()
        self.assertEqual(report.get("status"), "no_trades")

    def test_weekly_report_with_data(self):
        self.registry.open_trade(self._signal_data(signal_id="SIG-W1"))
        self.registry.close_trade("SIG-W1", "WIN", lucro_usdt=50, retorno_pct=1.0, r_multiple=2.0)

        report = self.registry.get_weekly_report()
        self.assertEqual(report["total"], 1)
        self.assertIsNotNone(report.get("win_rate"))
        self.assertIn("BTCUSDT", str(report.get("best_asset", "")))

    def test_open_trades_empty(self):
        self.assertEqual(len(self.registry.get_open_trades()), 0)

    def test_open_trade_with_operational_dict(self):
        data = self._signal_data(signal_id="SIG-OP1")
        data["operational"] = {
            "leverage": 20,
            "account_size": 200,
            "capital_per_trade": 60,
            "collateral": 60,
            "position_value": 1200,
            "profit_est": 24,
            "loss_est": 12,
        }
        trade_id = self.registry.open_trade(data)
        self.assertIsNotNone(trade_id)

        trades = self.registry.get_open_trades()
        self.assertEqual(len(trades), 1)

    def test_breakeven_trade(self):
        self.registry.open_trade(self._signal_data(signal_id="SIG-BE1"))
        self.registry.close_trade("SIG-BE1", "BREAKEVEN", lucro_usdt=0, perda_usdt=0, retorno_pct=0.0)

        stats = self.registry.get_statistics()
        self.assertEqual(stats["breakeven_trades"], 1)

    def test_multiple_opens_and_closes(self):
        for i in range(5):
            self.registry.open_trade(self._signal_data(signal_id=f"SIG-M{i}", symbol=f"PAIR{i}"))
        self.assertEqual(len(self.registry.get_open_trades()), 5)

        for i in range(5):
            self.registry.close_trade(f"SIG-M{i}", "WIN" if i % 2 == 0 else "LOSS", lucro_usdt=10 if i % 2 == 0 else 0, perda_usdt=5 if i % 2 != 0 else 0)

        self.assertEqual(len(self.registry.get_open_trades()), 0)
        self.assertEqual(len(self.registry.get_closed_trades()), 5)

    def test_loss_analysis_multiple_gates(self):
        self.registry.open_trade(self._signal_data(
            signal_id="SIG-LA1", quality_score=0.50, confidence_score=0.90,
            consensus_score=0.85, overall_score_value=60, risk_reward=1.2,
        ))
        self.registry.close_trade("SIG-LA1", "LOSS", perda_usdt=30, retorno_pct=-2.5)

        loss = self.registry.get_loss_analysis()
        self.assertEqual(loss["total_losses"], 1)
        reasons = loss["analysis"][0]["reasons"]
        self.assertTrue(any("Quality" in r for r in reasons) or any("Score" in r for r in reasons))


if __name__ == '__main__':
    unittest.main()
