import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ENGINE.deduplication.signal_cache import (
    SignalCacheEngine,
    _get_candle_open,
    _is_small_change,
    TIMEFRAME_SECONDS,
)


class TestGetCandleOpen:
    def test_30m(self):
        ts = _get_candle_open("30m")
        assert ts % 1800 == 0
        assert ts <= time.time()

    def test_1h(self):
        ts = _get_candle_open("1h")
        assert ts % 3600 == 0

    def test_4h(self):
        ts = _get_candle_open("4h")
        assert ts % 14400 == 0

    def test_1d(self):
        ts = _get_candle_open("1d")
        assert ts % 86400 == 0

    def test_fallback(self):
        ts = _get_candle_open("unknown")
        assert ts % 3600 == 0


class TestIsSmallChange:
    def test_same_values(self):
        assert _is_small_change(100, 100, 1.0) is True

    def test_zero_values(self):
        assert _is_small_change(0, 0, 1.0) is True

    def test_small_pct(self):
        assert _is_small_change(100, 100.1, 0.20) is True

    def test_large_pct(self):
        assert _is_small_change(100, 101, 0.20) is False

    def test_one_zero(self):
        assert _is_small_change(0, 100, 1.0) is False


class TestSignalCacheEngine:
    def setup_method(self):
        self.cache = SignalCacheEngine()

    def test_can_send_new_signal(self):
        assert self.cache.can_send("BTCUSDT", "1h", "LONG") is True

    def test_can_send_after_mark(self):
        self.cache.mark_sent("BTCUSDT", "1h", "LONG")
        assert self.cache.can_send("BTCUSDT", "1h", "LONG") is False

    def test_can_send_different_symbol(self):
        self.cache.mark_sent("BTCUSDT", "1h", "LONG")
        assert self.cache.can_send("ETHUSDT", "1h", "LONG") is True

    def test_can_send_different_timeframe(self):
        self.cache.mark_sent("BTCUSDT", "1h", "LONG")
        assert self.cache.can_send("BTCUSDT", "4h", "LONG") is True

    def test_can_send_different_direction(self):
        self.cache.mark_sent("BTCUSDT", "1h", "LONG")
        # Reversal should be allowed
        assert self.cache.can_send("BTCUSDT", "1h", "SHORT") is True

    def test_small_entry_change(self):
        data = {"entry_price": 100.0, "quality": 0.75, "probability": 0.65}
        self.cache.mark_sent("BTCUSDT", "1h", "LONG", data)
        # Same entry, small change
        data2 = {"entry_price": 100.05, "quality": 0.76, "probability": 0.66}
        assert self.cache.can_send("BTCUSDT", "1h", "LONG", data2) is False

    def test_large_entry_change(self):
        data = {"entry_price": 100.0, "quality": 0.75, "probability": 0.65}
        self.cache.mark_sent("BTCUSDT", "1h", "LONG", data)
        # Different entry (>0.20%)
        data2 = {"entry_price": 101.0, "quality": 0.76, "probability": 0.66}
        assert self.cache.can_send("BTCUSDT", "1h", "LONG", data2) is True

    def test_is_different_setup(self):
        self.cache.mark_sent("BTCUSDT", "1h", "LONG", {"entry_price": 100.0})
        assert self.cache.is_different_setup("BTCUSDT", "1h", "LONG", 100.05) is False
        assert self.cache.is_different_setup("BTCUSDT", "1h", "LONG", 101.0) is True

    def test_is_same_candle(self):
        self.cache.mark_sent("BTCUSDT", "1h", "LONG")
        assert self.cache.is_same_candle("1h") is True
        # Different timeframe - may be different candle
        result = self.cache.is_same_candle("30m")
        assert isinstance(result, bool)

    def test_cleanup(self):
        self.cache.mark_sent("BTCUSDT", "1h", "LONG")
        assert len(self.cache._cache) == 1
        self.cache._cleanup(max_age=0)
        assert len(self.cache._cache) == 0

    def test_mark_seen(self):
        self.cache.mark_seen("BTCUSDT", "1h", "LONG")
        assert self.cache.can_send("BTCUSDT", "1h", "LONG") is False

    def test_mark_seen_with_data(self):
        self.cache.mark_seen("BTCUSDT", "1h", "LONG", {"entry_price": 100.0})
        key = f"BTCUSDT_1h_LONG_{_get_candle_open('1h')}"
        assert self.cache._entry_price.get(key) == 100.0

    def test_probability_as_dict(self):
        data = {"entry_price": 100.0, "quality": 0.75, "probability": {"probability": 0.65}}
        self.cache.mark_sent("BTCUSDT", "1h", "LONG", data)
        assert self.cache.can_send("BTCUSDT", "1h", "LONG", data) is False

    def test_new_candle_invalidates(self):
        old_open = _get_candle_open("1h") - 3600
        key = f"BTCUSDT_1h_LONG_{old_open}"
        # Manually insert old candle only (not current candle)
        self.cache._cache[key] = {"timestamp": time.time(), "candle_open": old_open, "direction": "LONG"}
        self.cache._entry_price[key] = 100.0
        self.cache._quality[key] = 0.75
        self.cache._probability[key] = 0.65
        # Should be allowed (different candle — no entry for current candle)
        assert self.cache.can_send("BTCUSDT", "1h", "LONG") is True

    def test_timframe_seconds_dict(self):
        assert TIMEFRAME_SECONDS["30m"] == 1800
        assert TIMEFRAME_SECONDS["1h"] == 3600
        assert TIMEFRAME_SECONDS["4h"] == 14400
        assert TIMEFRAME_SECONDS["1d"] == 86400
