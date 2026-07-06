import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from CORE.events.event_bus import EventBus
from CORE.events.events import Event, EventTypes
from ENGINE.market.market_engine import MarketEngine
from ENGINE.scanner.scanner_engine import ScannerEngine
from ENGINE.backtest.backtest_engine import BacktestEngine
from AI.learning.learning_engine import LearningEngine
from AI.evolution.optimizer import EvolutionEngine
from AI.validation.decision_validator import DecisionValidator
from CORE.memory.memory_engine import MemoryEngine
from .bot_config import BotConfig
from BOTS.mexc.bot_types import (
    Balance, BotEvent, BotStatus, ConnectionInfo, ConnectionStatus, DailyStats, MonitoringSnapshot,
    OrderSide, OrderStatus, Position, SignalApproval,
)
from .exchange.connector import ExchangeConnector
from .execution.break_even_manager import BreakEvenManager
from .execution.order_executor import OrderExecutor
from .execution.position_monitor import PositionMonitor
from .execution.stop_manager import StopManager
from .execution.take_profit_manager import TakeProfitManager
from .execution.trailing_stop_manager import TrailingStopManager
from .notification.engine import NotificationEngine
from .protection.emergency import EmergencyProtection
from .protection.recovery import RecoveryEngine
from .signals.signal_receiver import SignalReceiver, SignalData
from .signals.signal_validator import SignalValidator
from .trading.execution_engine import ExecutionEngine
from .trading.order_manager import OrderManager
from .trading.position_manager import BotPositionManager
from .trading.risk_manager import BotRiskManager

log = logging.getLogger(__name__)


class BotEngine:
    def __init__(self, config: Optional[BotConfig] = None, event_bus: Optional[EventBus] = None,
                 market_engine: Optional[MarketEngine] = None, scanner_engine: Optional[ScannerEngine] = None,
                 backtest_engine: Optional[BacktestEngine] = None):
        self._config = config or BotConfig()
        self._bus = event_bus or EventBus()
        self._market = market_engine or MarketEngine()
        self._scanner = scanner_engine or ScannerEngine()
        self._backtest = backtest_engine or BacktestEngine()

        # Initialize modular architecture
        self._exchange = ExchangeConnector(self._config)
        self._om = OrderManager(self._config, self._exchange)
        self._pm = BotPositionManager(self._config, self._exchange)
        self._rm = BotRiskManager(self._config, self._pm)
        self._monitor = PositionMonitor(self._config, self._exchange, self._pm)

        self._sm = StopManager(self._config, self._om)
        self._tpm = TakeProfitManager(self._config, self._om)
        self._ee = ExecutionEngine(self._config, self._exchange, self._om, self._pm,
                                    self._rm, self._monitor, self._tpm)

        self._receiver = SignalReceiver(self._config)
        self._validator = SignalValidator(self._config)

        self._executor = OrderExecutor(self._config, self._om, self._pm)
        self._bem = BreakEvenManager(self._config, self._sm)
        self._tsm = TrailingStopManager(self._config, self._sm)

        self._ep = EmergencyProtection(self._config, self._pm, self._ee)
        self._recovery = RecoveryEngine(self._config, self._exchange, self._om, self._pm)
        self._notify = NotificationEngine(self._config, self._bus)

        self._status = BotStatus.STOPPED
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._balance = Balance()

        # Wire up receivers and callbacks
        self._receiver.register_callback(self._on_signal_received)
        self._bus.subscribe(EventTypes.SIGNAL_GENERATED, self._on_scanner_signal_generated)

    @property
    def status(self) -> BotStatus:
        return self._status

    @property
    def exchange(self) -> ExchangeConnector:
        return self._exchange

    @property
    def order_manager(self) -> OrderManager:
        return self._om

    @property
    def position_manager(self) -> BotPositionManager:
        return self._pm

    @property
    def risk_manager(self) -> BotRiskManager:
        return self._rm

    @property
    def execution_engine(self) -> ExecutionEngine:
        return self._ee

    @property
    def signal_receiver(self) -> SignalReceiver:
        return self._receiver

    @property
    def signal_validator(self) -> SignalValidator:
        return self._validator

    @property
    def emergency_protection(self) -> EmergencyProtection:
        return self._ep

    @property
    def recovery_engine(self) -> self:
        return self._recovery

    @property
    def notification_engine(self) -> NotificationEngine:
        return self._notify

    def start(self) -> bool:
        if self._running:
            return True
        log.info("BotEngine: starting MEXC Bot...")
        self._status = BotStatus.RUNNING
        self._running = True

        # Initial connection
        self._exchange.connect(self._config.mexc_api_key, self._config.mexc_api_secret)

        # Initialize risk starting balance
        self._update_balance()
        self._rm.initialize_day(self._balance.total)

        # Start processing thread
        self._thread = threading.Thread(target=self._run_loop, name="MEXC_Bot_Thread", daemon=True)
        self._thread.start()

        self._bus.publish(Event(type=EventTypes.ENGINE_START, data={"exchange": "MEXC"}))
        log.info("BotEngine: MEXC Bot started successfully")
        return True

    def stop(self) -> None:
        if not self._running:
            return
        log.info("BotEngine: stopping MEXC Bot...")
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        self._exchange.disconnect()
        self._status = BotStatus.STOPPED
        self._bus.publish(Event(type=EventTypes.ENGINE_STOP, data={"exchange": "MEXC"}))
        log.info("BotEngine: MEXC Bot stopped")

    def pause(self) -> None:
        self._status = BotStatus.PAUSED
        log.info("BotEngine: MEXC Bot paused")

    def resume(self) -> None:
        self._status = BotStatus.RUNNING
        log.info("BotEngine: MEXC Bot resumed")

    def trigger_emergency_shutdown(self) -> None:
        self._status = BotStatus.ERROR
        self._ep.trigger_emergency_close()
        self._notify.notify_error("EMERGENCY SHUTDOWN TRIGGERED")

    def get_monitoring_snapshot(self) -> MonitoringSnapshot:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        daily = self._rm.get_daily_stats(today) or DailyStats(date=today)
        conn = ConnectionInfo(
            websocket=self._exchange.ws.status,
            api=self._exchange.api.status,
            latency_ms=self._exchange.api.last_latency_ms,
            last_heartbeat=datetime.now(timezone.utc),
        )
        return MonitoringSnapshot(
            positions=self._pm.get_open_count(),
            orders=len(self._om.get_open_orders()),
            balance=self._balance,
            connection=conn,
            daily_stats=daily,
            circuit_breaker_active=self._rm.circuit_breaker.active,
            daily_drawdown=self._rm._current_daily_drawdown(self._balance.total),
        )

    def _run_loop(self) -> None:
        last_sync = 0.0
        last_heartbeat = 0.0

        while self._running:
            try:
                if self._status in (BotStatus.PAUSED, BotStatus.ERROR):
                    time.sleep(1)
                    continue

                now = time.time()

                # Process positions monitor and price updates
                self._monitor.monitor_all()

                # Update balance and risk metrics
                self._update_balance()
                self._rm.update_peak(self._balance.total)

                # Check protections (emergency limits, drawdown, risk)
                if self._ep.check_protections(self._balance.total):
                    self._status = BotStatus.ERROR
                    continue

                # Manage active positions (trail, SL, BE, TP)
                self._manage_active_positions()

                # Recovery/Sync interval
                if now - last_sync >= self._config.sync_interval_seconds:
                    self._recovery.sync_orders()
                    self._recovery.sync_positions()
                    last_sync = now

                # Connection check/heartbeat
                if now - last_heartbeat >= self._config.heartbeat_interval_seconds:
                    if not self._exchange.is_connected:
                        self._status = BotStatus.RECOVERING
                        self._recovery.handle_disconnect()
                        if self._exchange.is_connected:
                            self._status = BotStatus.RUNNING
                            self._notify.notify_reconnection(True)
                        else:
                            self._status = BotStatus.ERROR
                            self._notify.notify_reconnection(False)
                    last_heartbeat = now

                time.sleep(1)

            except Exception as e:
                log.exception("BotEngine: error in run loop")
                self._notify.notify_error(f"Run loop exception: {e}")
                time.sleep(2)

    def _update_balance(self) -> None:
        if self._config.dry_run:
            self._balance = Balance(total=10000.0, free=10000.0, used=0.0)
        else:
            try:
                self._balance = self._exchange.get_balance()
            except Exception:
                pass

    def _manage_active_positions(self) -> None:
        for pos in list(self._pm.all_positions()):
            if pos.quantity <= 0:
                continue

            current_price = pos.current_price

            # Baseline v4.0 — Revalidação Contínua
            exit_result = self._ee.revalidate_and_maybe_exit(
                pos, current_price,
                structure_broken=False,
                regime_changed=False,
                bos_contrario=False,
                choch_contrario=False,
            )
            if exit_result:
                self._rm.record_trade_result(pos.unrealized_pnl)
                continue

            # 1. Check stop loss
            if self._sm.check_and_adjust_stop(pos, current_price):
                self._ee.close_position_market(pos.id)
                self._rm.record_trade_result(pos.unrealized_pnl)
                self._notify.notify_stop_hit(pos, current_price)
                continue

            # 2. Check take profit (partial or full)
            hit, pct = self._tpm.check_take_profit(pos, current_price)
            if hit:
                if pct >= 1.0:
                    self._ee.close_position_market(pos.id)
                    self._rm.record_trade_result(pos.unrealized_pnl)
                    self._notify.notify_tp2_hit(pos, current_price)
                else:
                    partial_qty = pos.quantity * pct
                    close_side = OrderSide.SELL if pos.side == OrderSide.BUY else OrderSide.BUY
                    self._om.create_market_order(pos.pair, close_side, partial_qty, reduce_only=True)
                    pos.quantity -= partial_qty
                    self._notify.notify_tp1_hit(pos, current_price)
                continue

            # 3. Check break even
            if self._bem.check_and_apply_break_even(pos, current_price):
                self._notify.notify_break_even(pos)

            # 4. Check trailing stop
            if self._tsm.check_and_apply_trailing_stop(pos, current_price):
                log.info("BotEngine: trailing stop adjusted for %s", pos.pair)

    def _on_scanner_signal_generated(self, event: Event) -> None:
        if self._status != BotStatus.RUNNING:
            return
        log.info("BotEngine: received scanner event: %s", event.type)
        self._receiver.receive_signal(event.data)

    def _on_signal_received(self, signal: SignalData) -> None:
        if self._status != BotStatus.RUNNING:
            return

        # 1. Validation phase (Baseline v4.0 — full institutional gate)
        market_ctx = self._market.get_market_context(signal.pair) if hasattr(self._market, 'get_market_context') else None
        approval, reasons = self._validator.validate(signal, signal.entry_price, market_ctx)
        if approval != SignalApproval.APPROVED:
            log.warning("BotEngine v4.0: signal rejected (%d reasons): %s", len(reasons), "; ".join(reasons))
            return

        # 2. Market Intelligence regime check
        if signal.regime.lower() in ("ranging", "volatile") and not self._config.reentry_enabled:
            log.warning("BotEngine v4.0: signal rejected by Market Intelligence regime filter (%s)", signal.regime)
            return

        # 3. Backtest check
        bt_stats = self._backtest.last_result()
        if bt_stats and bt_stats.win_rate < self._config.min_confidence:
            log.warning("BotEngine v4.0: signal rejected by Backtest (Win Rate %.2f < %.2f)",
                        bt_stats.win_rate, self._config.min_confidence)
            return

        # 4. Risk / Position sizing
        balance = self._balance.total
        qty = self._rm.calculate_position_size(balance, signal.entry_price, signal.stop_loss)
        if qty <= 0:
            log.warning("BotEngine v4.0: position size = 0 for %s", signal.pair)
            return

        # 5. Validate TP targets before execution
        dummy_position = self._pm.create_dummy(signal)
        targets_valid, reason = self._tpm.validate_targets(dummy_position, signal.score, market_ctx)
        if not targets_valid:
            log.warning("BotEngine v4.0: TP targets invalid for %s: %s", signal.pair, reason)
            return

        # 6. Execution phase
        log.info("BotEngine v4.0: executing signal for %s", signal.pair)
        if signal.order_side == OrderSide.BUY:
            res = self._ee.execute_long(
                signal.pair, signal.entry_price, signal.stop_loss,
                signal.take_profit_1, signal.take_profit_2,
                qty, signal.signal_id, atr=signal.atr, setup=signal.setup,
                regime=signal.regime, signal_score=signal.score, market_ctx=market_ctx,
            )
        else:
            res = self._ee.execute_short(
                signal.pair, signal.entry_price, signal.stop_loss,
                signal.take_profit_1, signal.take_profit_2,
                qty, signal.signal_id, atr=signal.atr, setup=signal.setup,
                regime=signal.regime, signal_score=signal.score, market_ctx=market_ctx,
            )

        if res.success and res.position:
            self._notify.notify_trade_opened(res.position)
        else:
            self._notify.notify_error(f"Execution failed for {signal.pair}: {res.error}")
