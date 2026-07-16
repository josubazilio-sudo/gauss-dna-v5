import sys
import os
import json
import tempfile
import inspect

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import unittest
from ENGINE.watchlist.watchlist_manager import (
    WatchlistManager, WATCHLIST_PRIORITY_BONUS,
)


_TEST_SYMBOLS = [
    "SPCXUSDT", "EPICUSDT", "HOMEUSDT", "SKYAIUSDT", "SOLUSDT",
    "OPGUSDT", "WLDUSDT", "ALLOUSDT", "HUSDT", "BEATUSDT",
]


def _make_watchlist_file(symbols=None):
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8",
    )
    json.dump({"symbols": symbols or _TEST_SYMBOLS}, tmp)
    tmp.close()
    return tmp.name


class TestWatchlistManagerLoad(unittest.TestCase):

    def tearDown(self):
        if hasattr(self, "_tmpfile") and self._tmpfile:
            try:
                os.unlink(self._tmpfile)
            except OSError:
                pass

    def test_load_valid_file(self):
        self._tmpfile = _make_watchlist_file()
        wm = WatchlistManager(path=self._tmpfile)
        self.assertTrue(wm._loaded)
        self.assertEqual(len(wm.symbols), 10)
        self.assertIn("SOLUSDT", wm.symbols)
        self.assertIn("SPCXUSDT", wm.symbols)

    def test_load_orders_preserved(self):
        self._tmpfile = _make_watchlist_file()
        wm = WatchlistManager(path=self._tmpfile)
        expected = _TEST_SYMBOLS
        self.assertEqual(wm.ordered, expected)

    def test_load_normalizes_case(self):
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8",
        )
        json.dump({"symbols": ["solusdt", "Btcusdt", "EthUSDT"]}, tmp)
        tmp.close()
        wm = WatchlistManager(path=tmp.name)
        self.assertIn("SOLUSDT", wm.symbols)
        self.assertIn("BTCUSDT", wm.symbols)
        self.assertIn("ETHUSDT", wm.symbols)
        os.unlink(tmp.name)

    def test_load_missing_file(self):
        wm = WatchlistManager(path="/nonexistent/path/watchlist.json")
        self.assertTrue(wm._loaded)
        self.assertEqual(len(wm.symbols), 0)

    def test_load_empty_symbols(self):
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8",
        )
        json.dump({"symbols": []}, tmp)
        tmp.close()
        wm = WatchlistManager(path=tmp.name)
        self.assertEqual(len(wm.symbols), 0)
        os.unlink(tmp.name)

    def test_load_invalid_json(self):
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8",
        )
        tmp.write("{invalid json")
        tmp.close()
        wm = WatchlistManager(path=tmp.name)
        self.assertEqual(len(wm.symbols), 0)
        os.unlink(tmp.name)

    def test_reload_updates_symbols(self):
        tmp = _make_watchlist_file(["BTCUSDT"])
        wm = WatchlistManager(path=tmp)
        self.assertIn("BTCUSDT", wm.symbols)
        self.assertEqual(len(wm.symbols), 1)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"symbols": ["ETHUSDT", "SOLUSDT"]}, f)
        wm.reload()
        self.assertNotIn("BTCUSDT", wm.symbols)
        self.assertIn("ETHUSDT", wm.symbols)
        self.assertIn("SOLUSDT", wm.symbols)
        self.assertEqual(len(wm.symbols), 2)
        os.unlink(tmp)


class TestWatchlistManagerIsWatchlist(unittest.TestCase):

    def setUp(self):
        self._tmpfile = _make_watchlist_file()
        self.wm = WatchlistManager(path=self._tmpfile)

    def tearDown(self):
        os.unlink(self._tmpfile)

    def test_is_watchlist_positive(self):
        for s in _TEST_SYMBOLS:
            self.assertTrue(self.wm.is_watchlist(s), f"{s} should be watchlist")

    def test_is_watchlist_negative(self):
        self.assertFalse(self.wm.is_watchlist("BTCUSDT"))

    def test_is_watchlist_case_insensitive(self):
        self.assertTrue(self.wm.is_watchlist("solusdt"))

    def test_is_watchlist_empty_list(self):
        tmp = _make_watchlist_file([])
        wm = WatchlistManager(path=tmp)
        self.assertFalse(wm.is_watchlist("ANYUSDT"))
        os.unlink(tmp)


class TestWatchlistManagerReorderScanQueue(unittest.TestCase):

    def setUp(self):
        self._tmpfile = _make_watchlist_file()
        self.wm = WatchlistManager(path=self._tmpfile)

    def tearDown(self):
        os.unlink(self._tmpfile)

    def test_reorder_puts_watchlist_first(self):
        scan_list = ["BTCUSDT", "SOLUSDT", "ETHUSDT", "SPCXUSDT", "XRPUSDT"]
        ordered = self.wm.reorder_scan_queue(scan_list)
        self.assertEqual(ordered[0], "SOLUSDT")
        self.assertEqual(ordered[1], "SPCXUSDT")
        self.assertIn("BTCUSDT", ordered[2:])
        self.assertIn("ETHUSDT", ordered[2:])
        self.assertIn("XRPUSDT", ordered[2:])

    def test_reorder_preserves_all_pairs(self):
        scan_list = ["BTCUSDT", "SOLUSDT", "ETHUSDT", "SPCXUSDT", "XRPUSDT"]
        ordered = self.wm.reorder_scan_queue(scan_list)
        self.assertEqual(len(ordered), len(scan_list))
        self.assertEqual(set(ordered), set(scan_list))

    def test_reorder_all_watchlist(self):
        ordered = self.wm.reorder_scan_queue(list(_TEST_SYMBOLS))
        self.assertEqual(ordered, _TEST_SYMBOLS)

    def test_reorder_no_watchlist(self):
        scan_list = ["BTCUSDT", "ETHUSDT", "XRPUSDT"]
        ordered = self.wm.reorder_scan_queue(scan_list)
        self.assertEqual(ordered, scan_list)

    def test_reorder_empty(self):
        ordered = self.wm.reorder_scan_queue([])
        self.assertEqual(ordered, [])

    def test_reorder_preserves_internal_order_among_watchlist(self):
        custom_order = ["WLDUSDT", "SOLUSDT", "HOMEUSDT"]
        scan_list = ["BTCUSDT", "WLDUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "HOMEUSDT"]
        ordered = self.wm.reorder_scan_queue(scan_list)
        wl_found = [s for s in ordered if s in custom_order]
        self.assertEqual(wl_found, custom_order)


class TestWatchlistManagerCountInList(unittest.TestCase):

    def setUp(self):
        self._tmpfile = _make_watchlist_file()
        self.wm = WatchlistManager(path=self._tmpfile)

    def tearDown(self):
        os.unlink(self._tmpfile)

    def test_count_all_watchlist(self):
        self.assertEqual(self.wm.count_in_list(_TEST_SYMBOLS), 10)

    def test_count_mixed(self):
        scan_list = ["BTCUSDT", "SOLUSDT", "ETHUSDT", "SPCXUSDT"]
        self.assertEqual(self.wm.count_in_list(scan_list), 2)

    def test_count_none(self):
        self.assertEqual(self.wm.count_in_list(["BTCUSDT", "ETHUSDT"]), 0)

    def test_count_empty(self):
        self.assertEqual(self.wm.count_in_list([]), 0)


class TestWatchlistPriorityBonus(unittest.TestCase):

    def setUp(self):
        self._tmpfile = _make_watchlist_file()
        self.wm = WatchlistManager(path=self._tmpfile)

    def tearDown(self):
        os.unlink(self._tmpfile)

    def test_bonus_for_watchlist(self):
        self.assertEqual(self.wm.get_priority_bonus("SOLUSDT"), WATCHLIST_PRIORITY_BONUS)

    def test_no_bonus_for_non_watchlist(self):
        self.assertEqual(self.wm.get_priority_bonus("BTCUSDT"), 0)

    def test_bonus_value_constant(self):
        self.assertEqual(WATCHLIST_PRIORITY_BONUS, 3)

    def test_bonus_case_insensitive(self):
        self.assertEqual(self.wm.get_priority_bonus("solusdt"), WATCHLIST_PRIORITY_BONUS)


class TestWatchlistStatsDict(unittest.TestCase):

    def setUp(self):
        self._tmpfile = _make_watchlist_file()
        self.wm = WatchlistManager(path=self._tmpfile)

    def tearDown(self):
        os.unlink(self._tmpfile)

    def test_stats_dict_keys(self):
        stats = self.wm.stats_dict()
        self.assertIn("total_watchlist", stats)
        self.assertIn("symbols", stats)
        self.assertEqual(stats["total_watchlist"], 10)

    def test_stats_symbols_preserve_order(self):
        stats = self.wm.stats_dict()
        self.assertEqual(stats["symbols"], _TEST_SYMBOLS)


class TestConfigFileExists(unittest.TestCase):

    def test_config_file_exists(self):
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config", "watchlist_priority.json",
        )
        self.assertTrue(os.path.isfile(config_path), f"Config file missing: {config_path}")

    def test_config_file_valid_json(self):
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config", "watchlist_priority.json",
        )
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("symbols", data)
        self.assertIsInstance(data["symbols"], list)
        self.assertGreater(len(data["symbols"]), 0)
        self.assertIn("SPCXUSDT", data["symbols"])
        self.assertIn("BEATUSDT", data["symbols"])

    def test_config_file_contains_all_initial_symbols(self):
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config", "watchlist_priority.json",
        )
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        expected = {"SPCXUSDT", "EPICUSDT", "HOMEUSDT", "SKYAIUSDT", "SOLUSDT",
                     "OPGUSDT", "WLDUSDT", "ALLOUSDT", "HUSDT", "BEATUSDT"}
        found = set(data["symbols"])
        self.assertEqual(found, expected)


class TestWatchlistPriorityBonusConstant(unittest.TestCase):

    def test_constant_never_affects_stats(self):
        from ENGINE.scanner.scanner_config import WATCHLIST_PRIORITY_BONUS as CFG_BONUS
        from ENGINE.watchlist.watchlist_manager import WATCHLIST_PRIORITY_BONUS as MGR_BONUS
        self.assertEqual(CFG_BONUS, MGR_BONUS)

    def test_constant_is_positive_small_int(self):
        self.assertIsInstance(WATCHLIST_PRIORITY_BONUS, int)
        self.assertGreater(WATCHLIST_PRIORITY_BONUS, 0)
        self.assertLess(WATCHLIST_PRIORITY_BONUS, 100)


class TestIntegrationWithPriorityScore(unittest.TestCase):

    def test_watchlist_does_not_affect_priority_score(self):
        from ENGINE.scanner.priority_score import compute_priority_score
        sig = inspect.signature(compute_priority_score)
        params = list(sig.parameters.keys())
        self.assertNotIn("watchlist", params,
            "compute_priority_score should NOT accept watchlist param")

    def test_watchlist_does_not_affect_decision_fields(self):
        from ENGINE.scanner.priority_score import compute_priority_score
        sig = inspect.signature(compute_priority_score)
        return_type = sig.return_annotation
        if return_type is not inspect.Parameter.empty and return_type is not float:
            self.fail("compute_priority_score should return float, not decision fields")

    def test_reorder_scan_queue_no_data_loss(self):
        tmp = _make_watchlist_file()
        wm = WatchlistManager(path=tmp)
        scan_list = [f"PAIR{i}USDT" for i in range(50)]
        scan_list[3] = "SOLUSDT"
        scan_list[17] = "SPCXUSDT"
        ordered = wm.reorder_scan_queue(scan_list)
        self.assertEqual(len(ordered), len(scan_list))
        self.assertEqual(set(ordered), set(scan_list))
        self.assertEqual(ordered[0], "SOLUSDT")
        self.assertEqual(ordered[1], "SPCXUSDT")
        os.unlink(tmp)


class TestTelegramIndicator(unittest.TestCase):

    def test_formatter_accepts_watchlist_field(self):
        from SERVICES.telegram.telegram_formatter import TelegramFormatter
        signal = {
            "symbol": "SOLUSDT", "timeframe": "1h", "direction": "LONG",
            "entry_price": 100.0, "stop_loss": 99.0, "take_profit_1": 102.0,
            "quality": 0.8, "quality_score": 0.8,
            "confidence": 0.7, "consensus": 0.7,
            "risk_reward": 2.0, "quantity": 1.0,
            "balance": 1000.0, "leverage": 10,
            "_watchlist_priority": True,
        }
        msg = TelegramFormatter.format_signal(signal, message_type="new")
        self.assertIn("WATCHLIST PRIORIT", msg)

    def test_formatter_no_watchlist_field(self):
        from SERVICES.telegram.telegram_formatter import TelegramFormatter
        signal = {
            "symbol": "BTCUSDT", "timeframe": "1h", "direction": "LONG",
            "entry_price": 100.0, "stop_loss": 99.0, "take_profit_1": 102.0,
            "quality": 0.8, "quality_score": 0.8,
            "confidence": 0.7, "consensus": 0.7,
            "risk_reward": 2.0, "quantity": 1.0,
            "balance": 1000.0, "leverage": 10,
            "_watchlist_priority": False,
        }
        msg = TelegramFormatter.format_signal(signal, message_type="new")
        self.assertNotIn("WATCHLIST PRIORIT", msg)

    def test_formatter_no_watchlist_key(self):
        from SERVICES.telegram.telegram_formatter import TelegramFormatter
        signal = {
            "symbol": "BTCUSDT", "timeframe": "1h", "direction": "LONG",
            "entry_price": 100.0, "stop_loss": 99.0, "take_profit_1": 102.0,
            "quality": 0.8, "quality_score": 0.8,
            "confidence": 0.7, "consensus": 0.7,
            "risk_reward": 2.0, "quantity": 1.0,
            "balance": 1000.0, "leverage": 10,
        }
        msg = TelegramFormatter.format_signal(signal, message_type="new")
        self.assertNotIn("WATCHLIST PRIORIT", msg)


if __name__ == "__main__":
    unittest.main()
