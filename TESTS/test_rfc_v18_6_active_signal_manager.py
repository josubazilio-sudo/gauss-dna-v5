import os
import json
import time
import pytest
from SERVICES.telegram.active_signal_manager import (
    ActiveSignalManager,
    ActiveOperation,
    Resolution,
    OperationStatus,
    _make_op_id,
    STATE_FILE,
    COOLDOWN_SECONDS,
)


# Fixture to reset singleton between tests
@pytest.fixture(autouse=True)
def reset_asm():
    ActiveSignalManager._instance = None
    ActiveSignalManager._initialized = False
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)
    yield
    ActiveSignalManager._instance = None
    ActiveSignalManager._initialized = False
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)


def _make_data(overrides=None):
    data = {
        "symbol": "BTCUSDT",
        "timeframe": "1H",
        "direction": "LONG",
        "entry_price": 50000.0,
        "stop_loss": 49000.0,
        "take_profit_1": 52000.0,
        "risk_reward": 2.0,
        "overall_score_value": 75.0,
        "quality_score": 70.0,
        "probability": {"probability": 65.0},
        "confidence": 80.0,
        "consensus_score": 70.0,
        "confluence_score": 65.0,
        "flow_score": 60.0,
        "liquidity_score": 55.0,
        "structure_score": 50.0,
        "risk_score": 30.0,
        "trend": "trending_up",
        "kalman_direction": "UP",
        "conviction_level": "Alta",
        "expectancy_level": "Alta",
        "coherence_score": {"coherence_score": 85},
    }
    if overrides:
        data.update(overrides)
    return data


class TestActiveSignalManager:

    def test_new_signal_resolution(self):
        asm = ActiveSignalManager()
        data = _make_data()
        res = asm.resolve("BTCUSDT", "1H", "LONG", data)
        assert res.action == "new"
        assert res.update_label is None

    def test_update_with_significant_change(self):
        asm = ActiveSignalManager()
        data1 = _make_data({"overall_score_value": 70.0})
        data2 = _make_data({"overall_score_value": 82.0})

        asm.create("BTCUSDT", "1H", "LONG", data1)
        asm.mark_sent("BTCUSDT_1H", data1)
        # Bypass cooldown for test
        asm._operations["BTCUSDT_1H"].last_update_ts = time.time() - COOLDOWN_SECONDS - 1

        res = asm.resolve("BTCUSDT", "1H", "LONG", data2)
        assert res.action == "send"
        assert res.update_label == "📈 SETUP FORTALECIDO"
        assert res.impact_score >= 50

    def test_ignore_small_change(self):
        asm = ActiveSignalManager()
        data1 = _make_data({"overall_score_value": 74.8})
        data2 = _make_data({"overall_score_value": 74.6})

        asm.create("BTCUSDT", "1H", "LONG", data1)
        asm.mark_sent("BTCUSDT_1H", data1)

        res = asm.resolve("BTCUSDT", "1H", "LONG", data2)
        assert res.action == "skip"
        assert res.skip_reason == "ignored"
        assert res.impact_score < 20

    def test_cooldown_blocks_update(self):
        asm = ActiveSignalManager()
        data1 = _make_data({"overall_score_value": 70.0})
        data2 = _make_data({"overall_score_value": 76.0})

        asm.create("BTCUSDT", "1H", "LONG", data1)
        asm.mark_sent("BTCUSDT_1H", data1)

        res = asm.resolve("BTCUSDT", "1H", "LONG", data2)
        assert res.action == "skip"
        assert res.skip_reason == "cooldown"

    def test_cooldown_bypass_with_critical_impact(self):
        asm = ActiveSignalManager()
        data1 = _make_data({"overall_score_value": 70.0})
        data2 = _make_data({"direction": "SHORT"})

        asm.create("BTCUSDT", "1H", "LONG", data1)
        asm.mark_sent("BTCUSDT_1H", data1)

        res = asm.resolve("BTCUSDT", "1H", "SHORT", data2)
        assert res.action == "reversal"
        assert res.update_label == "🔄 REVERSÃO DE TENDÊNCIA"

    def test_reversal_detected(self):
        asm = ActiveSignalManager()
        data1 = _make_data({"direction": "LONG"})
        data2 = _make_data({"direction": "SHORT"})

        asm.create("BTCUSDT", "1H", "LONG", data1)
        asm.mark_sent("BTCUSDT_1H", data1)

        res = asm.resolve("BTCUSDT", "1H", "SHORT", data2)
        assert res.action == "reversal"
        assert res.update_label == "🔄 REVERSÃO DE TENDÊNCIA"

        assert asm.get_active("BTCUSDT", "1H") is None

    def test_create_operation(self):
        asm = ActiveSignalManager()
        data = _make_data()
        op = asm.create("BTCUSDT", "1H", "LONG", data)
        assert op.operation_id == "BTCUSDT_1H"
        assert op.status == "ATIVA"
        assert op.asset == "BTCUSDT"
        assert op.timeframe == "1H"
        assert op.direction == "LONG"
        assert abs(op.score - 75.0) < 0.01
        assert op.last_sent_data is not None

        active = asm.get_active("BTCUSDT", "1H")
        assert active is not None
        assert active.operation_id == "BTCUSDT_1H"

    def test_mark_sent_updates_last_sent_data(self):
        asm = ActiveSignalManager()
        data1 = _make_data({"overall_score_value": 70.0})
        asm.create("BTCUSDT", "1H", "LONG", data1)

        data2 = _make_data({"overall_score_value": 85.0})
        asm.mark_sent("BTCUSDT_1H", data2)

        op = asm._operations["BTCUSDT_1H"]
        assert abs(op.score - 85.0) < 0.01
        assert op.last_sent_data["overall_score_value"] == 85.0

    def test_close_operation(self):
        asm = ActiveSignalManager()
        data = _make_data()
        op = asm.create("BTCUSDT", "1H", "LONG", data)
        assert asm.get_active("BTCUSDT", "1H") is not None

        asm.close("BTCUSDT_1H")
        assert op.status == "ENCERRADA"
        assert asm.get_active("BTCUSDT", "1H") is None

    def test_cancel_operation(self):
        asm = ActiveSignalManager()
        data = _make_data()
        asm.create("BTCUSDT", "1H", "LONG", data)
        assert asm.get_active("BTCUSDT", "1H") is not None

        asm.cancel("BTCUSDT_1H")
        op = asm._operations["BTCUSDT_1H"]
        assert op.status == "CANCELADA"
        assert asm.get_active("BTCUSDT", "1H") is None

    def test_new_signal_after_close(self):
        asm = ActiveSignalManager()
        data = _make_data()
        asm.create("BTCUSDT", "1H", "LONG", data)
        asm.close("BTCUSDT_1H")

        res = asm.resolve("BTCUSDT", "1H", "LONG", data)
        assert res.action == "new"

    def test_active_count(self):
        asm = ActiveSignalManager()
        data = _make_data()
        asm.create("BTCUSDT", "1H", "LONG", data)
        asm.create("ETHUSDT", "30m", "SHORT", data)
        assert asm.active_count() == 2

        asm.close("BTCUSDT_1H")
        assert asm.active_count() == 1

    def test_cleanup_expired(self):
        asm = ActiveSignalManager()
        data = _make_data()
        asm.create("BTCUSDT", "1H", "LONG", data)

        op = asm._operations["BTCUSDT_1H"]
        op.timestamp = time.time() - 73 * 3600

        count = asm.cleanup_expired()
        assert count == 1
        assert op.status == "ENCERRADA"
        assert asm.get_active("BTCUSDT", "1H") is None

    def test_get_recently_active_pairs(self):
        asm = ActiveSignalManager()
        data = _make_data()
        asm.create("BTCUSDT", "1H", "LONG", data)
        asm.create("ETHUSDT", "30m", "SHORT", data)

        pairs = asm.get_recently_active_pairs(window_hours=4.0)
        assert "BTCUSDT" in pairs
        assert "ETHUSDT" in pairs

    def test_singleton(self):
        asm1 = ActiveSignalManager()
        asm2 = ActiveSignalManager()
        assert asm1 is asm2

    def test_resolve_no_active_op_ignores_unrelated(self):
        asm = ActiveSignalManager()
        data = _make_data()
        asm.create("BTCUSDT", "1H", "LONG", data)

        res = asm.resolve("ETHUSDT", "30m", "SHORT", data)
        assert res.action == "new"

    def test_multiple_assets_independent(self):
        asm = ActiveSignalManager()
        data1 = _make_data({"symbol": "BTCUSDT", "timeframe": "1H"})
        data2 = _make_data({"symbol": "ETHUSDT", "timeframe": "30m"})

        asm.create("BTCUSDT", "1H", "LONG", data1)
        asm.create("ETHUSDT", "30m", "SHORT", data2)

        assert asm.active_count() == 2
        assert asm.get_active("BTCUSDT", "1H") is not None
        assert asm.get_active("ETHUSDT", "30m") is not None

    def test_persistence(self):
        asm = ActiveSignalManager()
        data = _make_data()
        asm.create("BTCUSDT", "1H", "LONG", data)
        asm.create("ETHUSDT", "30m", "SHORT", data)

        assert os.path.exists(STATE_FILE)
        with open(STATE_FILE, encoding="utf-8") as f:
            saved = json.load(f)
        assert len(saved) == 2

    def test_load_from_persistence(self):
        asm1 = ActiveSignalManager()
        data = _make_data()
        asm1.create("BTCUSDT", "1H", "LONG", data)

        ActiveSignalManager._instance = None
        ActiveSignalManager._initialized = False

        asm2 = ActiveSignalManager()
        assert asm2.get_active("BTCUSDT", "1H") is not None

    def test_make_op_id(self):
        assert _make_op_id("BTCUSDT", "1H") == "BTCUSDT_1H"
        assert _make_op_id("ethusdt", "30m") == "ETHUSDT_30m"
        assert _make_op_id("CHZUSDT", "1H") == "CHZUSDT_1H"
        assert _make_op_id("ADAUSDT", "30m") == "ADAUSDT_30m"


class TestActiveOperation:

    def test_is_expired(self):
        op = ActiveOperation(
            operation_id="BTCUSDT_1H",
            asset="BTCUSDT",
            timeframe="1H",
            direction="LONG",
            timestamp=time.time() - 73 * 3600,
        )
        assert op.is_expired() is True

    def test_not_expired(self):
        op = ActiveOperation(
            operation_id="BTCUSDT_1H",
            asset="BTCUSDT",
            timeframe="1H",
            direction="LONG",
            timestamp=time.time(),
        )
        assert op.is_expired() is False
