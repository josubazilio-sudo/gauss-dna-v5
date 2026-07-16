import unittest
import sys
import math
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from BOTS.mexc.bot_types import (
    Balance, BotEvent, BotStatus, ConnectionInfo, ConnectionStatus, DailyStats, MonitoringSnapshot,
    Order, OrderSide, OrderStatus, OrderType, Position, TimeInForce, SignalApproval,
)
from BOTS.mexc.bot_config import BotConfig
from BOTS.mexc.exchange.auth_manager import AuthenticationManager
from BOTS.mexc.exchange.api_manager import APIManager, APIError
from BOTS.mexc.exchange.websocket_manager import WebSocketManager
from BOTS.mexc.exchange.connector import ExchangeConnector
from BOTS.mexc.trading.order_manager import OrderManager
from BOTS.mexc.trading.position_manager import BotPositionManager
from BOTS.mexc.trading.risk_manager import BotRiskManager, CircuitBreaker
from BOTS.mexc.trading.execution_engine import ExecutionEngine
from BOTS.mexc.signals.signal_receiver import SignalReceiver, SignalData
from BOTS.mexc.signals.signal_validator import SignalValidator
from BOTS.mexc.execution.order_executor import OrderExecutor
from BOTS.mexc.execution.position_monitor import PositionMonitor
from BOTS.mexc.execution.stop_manager import StopManager
from BOTS.mexc.execution.take_profit_manager import TakeProfitManager
from BOTS.mexc.execution.break_even_manager import BreakEvenManager
from BOTS.mexc.execution.trailing_stop_manager import TrailingStopManager
from BOTS.mexc.protection.emergency import EmergencyProtection
from BOTS.mexc.protection.recovery import RecoveryEngine
from BOTS.mexc.notification.engine import NotificationEngine
from BOTS.mexc.bot_engine import BotEngine
from CORE.events.event_bus import EventBus
from CORE.events.events import Event


class TestAuthenticationManager(unittest.TestCase):
    def test_auth_flow(self):
        cfg = BotConfig()
        auth = AuthenticationManager(cfg)
        self.assertFalse(auth.authenticated)
        auth.authenticate("key", "secret")
        self.assertTrue(auth.authenticated)
        self.assertEqual(auth.api_key, "key")
        auth.clear()
        self.assertFalse(auth.authenticated)

    def test_sign_request(self):
        cfg = BotConfig()
        auth = AuthenticationManager(cfg)
        auth.authenticate("key", "secret")
        params = {"symbol": "BTCUSDT", "timestamp": 12345678}
        signed = auth.sign_request(params)
        self.assertIn("signature", signed)


class TestAPIManager(unittest.TestCase):
    @patch("urllib.request.urlopen")
    def test_ping(self, mock_urlopen):
        # Mock API response
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"{}"
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        cfg = BotConfig()
        auth = AuthenticationManager(cfg)
        api = APIManager(cfg, auth)
        self.assertEqual(api.status, ConnectionStatus.DISCONNECTED)
        self.assertTrue(api.connect())
        self.assertEqual(api.status, ConnectionStatus.CONNECTED)


class TestWebSocketManager(unittest.TestCase):
    def test_ws_flow(self):
        cfg = BotConfig()
        ws = WebSocketManager(cfg)
        self.assertEqual(ws.status, ConnectionStatus.DISCONNECTED)
        ws.connect()
        self.assertEqual(ws.status, ConnectionStatus.CONNECTED)

        cb_called = False
        def cb(data):
            nonlocal cb_called
            cb_called = True

        ws.subscribe("test_channel", cb)
        ws.on_message("test_channel", {"hello": "world"})
        self.assertTrue(cb_called)

        ws.disconnect()
        self.assertEqual(ws.status, ConnectionStatus.DISCONNECTED)


class TestExchangeConnector(unittest.TestCase):
    def test_connector_init(self):
        cfg = BotConfig()
        conn = ExchangeConnector(cfg)
        self.assertIsInstance(conn.auth, AuthenticationManager)
        self.assertIsInstance(conn.api, APIManager)
        self.assertIsInstance(conn.ws, WebSocketManager)


class TestOrderManager(unittest.TestCase):
    def setUp(self):
        self.cfg = BotConfig(dry_run=True)
        self.exchange = ExchangeConnector(self.cfg)
        self.om = OrderManager(self.cfg, self.exchange)

    def test_create_and_cancel_order(self):
        order = self.om.create_market_order("BTCUSDT", OrderSide.BUY, 0.5)
        self.assertIsNotNone(order)
        self.assertEqual(order.status, OrderStatus.FILLED)
        self.assertEqual(len(self.om.all_orders()), 1)

        # Stop order dry run should remain OPEN/PENDING until hit
        stop_order = self.om.create_stop_order("BTCUSDT", OrderSide.SELL, 0.5, 95.0)
        self.assertIsNotNone(stop_order)
        self.assertEqual(stop_order.status, OrderStatus.OPEN)

        self.om.cancel_order(stop_order.id)
        self.assertEqual(stop_order.status, OrderStatus.CANCELLED)


class TestBotPositionManager(unittest.TestCase):
    def setUp(self):
        self.cfg = BotConfig()
        self.exchange = ExchangeConnector(self.cfg)
        self.pm = BotPositionManager(self.cfg, self.exchange)

    def test_position_tracking(self):
        self.assertEqual(self.pm.get_open_count(), 0)
        self.assertTrue(self.pm.can_open_new())

        pos = self.pm.open_position(
            pair="BTCUSDT", side=OrderSide.BUY, quantity=1.0, entry_price=100.0,
            stop_loss=90.0, take_profit_1=110.0, take_profit_2=120.0,
        )
        self.assertEqual(self.pm.get_open_count(), 1)
        self.pm.update_position(pos.id, 105.0)
        self.assertEqual(pos.unrealized_pnl, 5.0)
        self.assertAlmostEqual(pos.pnl_percent(), 5.0)

        self.pm.close_position(pos.id, 110.0)
        self.assertEqual(self.pm.get_open_count(), 0)
        self.assertEqual(pos.realized_pnl, 10.0)


class TestBotRiskManager(unittest.TestCase):
    def setUp(self):
        self.cfg = BotConfig(max_positions=2, daily_position_limit=5)
        self.exchange = ExchangeConnector(self.cfg)
        self.pm = BotPositionManager(self.cfg, self.exchange)
        self.rm = BotRiskManager(self.cfg, self.pm)

    def test_circuit_breaker(self):
        cb = self.rm.circuit_breaker
        self.assertFalse(cb.active)
        cb.record_loss()
        cb.record_loss()
        self.assertFalse(cb.active)
        cb.record_loss() # 3 losses
        self.assertTrue(cb.active)
        cb.reset()
        self.assertFalse(cb.active)

    def test_risk_validations(self):
        self.rm.initialize_day(10000.0)
        self.assertTrue(self.rm.can_open_position(10000.0, 100.0, 0.0001))

        # Consecutive losses risk trigger
        for _ in range(3):
            self.rm.record_trade_result(-100.0)
        self.assertFalse(self.rm.can_open_position(10000.0, 100.0, 0.0001))

    def test_size_calculation(self):
        from ENGINE.scanner.scanner_config import ACCOUNT_SIZE
        size = self.rm.calculate_position_size(10000.0, 100.0, 90.0)
        # RFC V18.6: ACCOUNT_SIZE * leverage / entry_price
        # ACCOUNT_SIZE=200, leverage=25, entry=100 => 200*25/100 = 50
        expected = ACCOUNT_SIZE * self.rm._config.leverage / 100.0
        self.assertEqual(size, expected)


class TestExecutionEngine(unittest.TestCase):
    def setUp(self):
        self.cfg = BotConfig(dry_run=True)
        self.exchange = ExchangeConnector(self.cfg)
        self.om = OrderManager(self.cfg, self.exchange)
        self.pm = BotPositionManager(self.cfg, self.exchange)
        self.rm = BotRiskManager(self.cfg, self.pm)
        self.monitor = PositionMonitor(self.cfg, self.exchange, self.pm)
        self.tpm = TakeProfitManager(self.cfg, self.om)
        self.ee = ExecutionEngine(self.cfg, self.exchange, self.om, self.pm, self.rm, self.monitor, self.tpm)

    def test_execution_flow(self):
        res = self.ee.execute_long("BTCUSDT", 100.0, 90.0, 110.0, 120.0, 1.0)
        self.assertTrue(res.success)
        self.assertIsNotNone(res.position)
        self.assertEqual(self.pm.get_open_count(), 1)


class TestSignals(unittest.TestCase):
    def test_signals_receiver_and_validator(self):
        cfg = BotConfig(pairs=["BTCUSDT"], min_confidence=0.85, min_quality=0.85)
        receiver = SignalReceiver(cfg)
        validator = SignalValidator(cfg)

        raw_signal = {
            "ticker": "BTCUSDT", "direction": "long", "entry_price": "100.0",
            "stop_loss": "90.0", "take_profit_1": "120.0", "take_profit_2": "130.0",
            "timeframe": "1h", "setup": "bos", "regime": "trending_up",
            "confidence": "0.88", "quality": "0.88", "score": "0.88",
            "structural_score": "0.85", "entry_type": "pullback_ob",
            "classification": "ouro", "patterns": ["bos", "fvg"], "signal_id": "sig123",
            "false_breakout_clear": True, "traps_clear": True,
            "volume_above_avg": True, "rvol_confirmed": True,
            "no_absorption": True, "no_rejection": True, "structure_valid": True,
            "atr": "5.0",
        }

        signal = receiver.receive_signal(raw_signal)
        self.assertIsNotNone(signal)
        self.assertEqual(receiver.pending_count, 1)

        approval, reasons = validator.validate(signal, signal.entry_price, None)
        self.assertEqual(approval, SignalApproval.APPROVED)


class TestExecutionManagers(unittest.TestCase):
    def setUp(self):
        self.cfg = BotConfig(dry_run=True, break_even_activation_pct=0.02, trailing_stop_activation_pct=0.03, trailing_stop_distance_pct=0.01)
        self.exchange = ExchangeConnector(self.cfg)
        self.om = OrderManager(self.cfg, self.exchange)
        self.pm = BotPositionManager(self.cfg, self.exchange)
        self.sm = StopManager(self.cfg, self.om)
        self.tpm = TakeProfitManager(self.cfg, self.om)
        self.bem = BreakEvenManager(self.cfg, self.sm)
        self.tsm = TrailingStopManager(self.cfg, self.sm)

    def test_stop_hit(self):
        pos = self.pm.open_position("BTCUSDT", OrderSide.BUY, 1.0, 100.0, 95.0, 110.0, 120.0)
        self.assertFalse(self.sm.check_and_adjust_stop(pos, 98.0))
        self.assertTrue(self.sm.check_and_adjust_stop(pos, 94.0))

    def test_take_profit_hit(self):
        pos = self.pm.open_position("BTCUSDT", OrderSide.BUY, 1.0, 100.0, 95.0, 110.0, 120.0)
        hit, pct = self.tpm.check_take_profit(pos, 105.0)
        self.assertFalse(hit)

        hit, pct = self.tpm.check_take_profit(pos, 112.0)
        self.assertTrue(hit)
        self.assertEqual(pct, 0.5) # partial TP1

        hit, pct = self.tpm.check_take_profit(pos, 122.0)
        self.assertTrue(hit)
        self.assertEqual(pct, 1.0) # full TP2

    def test_break_even(self):
        pos = self.pm.open_position("BTCUSDT", OrderSide.BUY, 1.0, 100.0, 95.0, 110.0, 120.0)
        self.assertFalse(self.bem.check_and_apply_break_even(pos, 101.0))
        self.assertTrue(self.bem.check_and_apply_break_even(pos, 103.0)) # 3% gain > 2% activation
        self.assertEqual(pos.stop_loss, 100.0)

    def test_trailing_stop(self):
        pos = self.pm.open_position("BTCUSDT", OrderSide.BUY, 1.0, 100.0, 95.0, 110.0, 120.0)
        self.assertFalse(self.tsm.check_and_apply_trailing_stop(pos, 101.0))
        # 4% gain > 3% activation. Should activate.
        self.assertTrue(self.tsm.check_and_apply_trailing_stop(pos, 104.0))
        self.assertTrue(pos.trailing_stop_activated)
        # New SL = 104 * (1 - 0.01) = 102.96
        self.assertAlmostEqual(pos.stop_loss, 102.96)


class TestEmergencyAndRecovery(unittest.TestCase):
    def setUp(self):
        self.cfg = BotConfig(dry_run=True, emergency_stop_loss_pct=0.10)
        self.exchange = ExchangeConnector(self.cfg)
        self.om = OrderManager(self.cfg, self.exchange)
        self.pm = BotPositionManager(self.cfg, self.exchange)
        self.rm = BotRiskManager(self.cfg, self.pm)
        self.monitor = PositionMonitor(self.cfg, self.exchange, self.pm)
        self.tpm = TakeProfitManager(self.cfg, self.om)
        self.ee = ExecutionEngine(self.cfg, self.exchange, self.om, self.pm, self.rm, self.monitor, self.tpm)
        self.ep = EmergencyProtection(self.cfg, self.pm, self.ee)
        self.recovery = RecoveryEngine(self.cfg, self.exchange, self.om, self.pm)

    def test_emergency_drawdown(self):
        pos = self.pm.open_position("BTCUSDT", OrderSide.BUY, 1.0, 100.0, 95.0, 110.0, 120.0)
        pos.unrealized_pnl = -1200.0 # 12% DD on 10000 balance
        self.assertTrue(self.ep.check_protections(10000.0))
        self.assertTrue(self.ep.triggered)
        self.assertEqual(self.pm.get_open_count(), 0)

    def test_recovery_flow(self):
        pos = self.pm.open_position("BTCUSDT", OrderSide.BUY, 1.0, 100.0, 95.0, 110.0, 120.0)
        # Recovery should make sure stop order exists.
        self.recovery.sync_positions()
        # Verify stop order was created in order manager
        self.assertGreater(len(self.om.all_orders()), 0)


class TestBotEngine(unittest.TestCase):
    def test_public_balance_property(self):
        bus = EventBus()
        cfg = BotConfig(dry_run=True, pairs=["BTCUSDT"])
        bot = BotEngine(cfg, bus)

        self.assertIsInstance(bot.balance, Balance)

    def test_full_bot_flow(self):
        bus = EventBus()
        cfg = BotConfig(dry_run=True, pairs=["BTCUSDT"])
        bot = BotEngine(cfg, bus)

        # Test initial states
        self.assertEqual(bot.status, BotStatus.STOPPED)
        bot.start()
        self.assertEqual(bot.status, BotStatus.RUNNING)

        # Trigger mock signal via event bus (Baseline v4.0 compliant)
        bus.publish(Event(
            type="signal.generated",
            data={
                "ticker": "BTCUSDT", "direction": "long", "entry_price": "100.0",
                "stop_loss": "90.0", "take_profit_1": "120.0", "take_profit_2": "130.0",
                "timeframe": "1h", "setup": "bos", "regime": "trending_up",
                "confidence": "0.88", "quality": "0.88", "score": "0.88",
                "structural_score": "0.85", "entry_type": "pullback_ob",
                "classification": "ouro", "patterns": ["bos"], "signal_id": "sig123",
                "false_breakout_clear": True, "traps_clear": True,
                "volume_above_avg": True, "rvol_confirmed": True,
                "no_absorption": True, "no_rejection": True, "structure_valid": True,
                "atr": "5.0",
            }
        ))

        # Give it a tiny slice of time
        time.sleep(0.1)

        # Verify position was opened
        self.assertEqual(bot.position_manager.get_open_count(), 1)
        pos = bot.position_manager.get_position_by_pair("BTCUSDT")
        self.assertIsNotNone(pos)

        # Retrieve snapshot
        snap = bot.get_monitoring_snapshot()
        self.assertEqual(snap.positions, 1)

        # Shut down
        bot.stop()
        self.assertEqual(bot.status, BotStatus.STOPPED)


if __name__ == "__main__":
    unittest.main()
