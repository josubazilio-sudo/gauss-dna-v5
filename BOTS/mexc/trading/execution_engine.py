import logging
from typing import Any, Dict, List, Optional, Tuple

from ..bot_config import BotConfig
from ..bot_types import Order, OrderSide, OrderStatus, OrderType, Position, TimeInForce
from ..exchange.connector import ExchangeConnector
from ..execution.position_monitor import PositionMonitor
from ..execution.take_profit_manager import TakeProfitManager
from .order_manager import OrderManager
from .position_manager import BotPositionManager
from .risk_manager import BotRiskManager

log = logging.getLogger(__name__)


class ExecutionResult:
    def __init__(self, success: bool, order: Optional[Order] = None,
                 position: Optional[Position] = None, error: str = ""):
        self.success = success
        self.order = order
        self.position = position
        self.error = error


class ExecutionEngine:
    def __init__(self, config: BotConfig, exchange: ExchangeConnector,
                 order_manager: OrderManager, position_manager: BotPositionManager,
                 risk_manager: BotRiskManager, position_monitor: PositionMonitor,
                 take_profit_manager: TakeProfitManager):
        self._config = config
        self._exchange = exchange
        self._om = order_manager
        self._pm = position_manager
        self._rm = risk_manager
        self._monitor = position_monitor
        self._tpm = take_profit_manager

    def execute_long(self, pair: str, entry_price: float, stop_loss: float,
                     take_profit_1: float, take_profit_2: float,
                     quantity: float, signal_id: str = "", atr: float = 0.0,
                     setup: str = "", regime: str = "",
                     signal_score: float = 0.0, market_ctx: Any = None) -> ExecutionResult:
        return self._execute(pair, OrderSide.BUY, entry_price, stop_loss,
                             take_profit_1, take_profit_2, quantity,
                             signal_id, atr, setup, regime, signal_score, market_ctx)

    def execute_short(self, pair: str, entry_price: float, stop_loss: float,
                      take_profit_1: float, take_profit_2: float,
                      quantity: float, signal_id: str = "", atr: float = 0.0,
                      setup: str = "", regime: str = "",
                      signal_score: float = 0.0, market_ctx: Any = None) -> ExecutionResult:
        return self._execute(pair, OrderSide.SELL, entry_price, stop_loss,
                             take_profit_1, take_profit_2, quantity,
                             signal_id, atr, setup, regime, signal_score, market_ctx)

    def _execute(self, pair: str, side: OrderSide, entry_price: float,
                 stop_loss: float, take_profit_1: float, take_profit_2: float,
                 quantity: float, signal_id: str, atr: float,
                 setup: str, regime: str, signal_score: float,
                 market_ctx: Any) -> ExecutionResult:
        pair_side = f"{side.value.upper()} {pair}"
        if quantity <= 0:
            return ExecutionResult(False, error="Invalid quantity")

        spread = self._estimate_spread(pair)
        bal = self._exchange.get_balance().total
        if not self._rm.can_open_position(bal, entry_price, spread):
            return ExecutionResult(False, error="Risk check failed")

        order = self._om.create_market_order(pair, side, quantity, signal_id, entry_price=entry_price)
        if not order:
            return ExecutionResult(False, error="Order creation failed")

        fill_price = order.average_fill_price if order.average_fill_price > 0 else entry_price
        position = self._pm.open_position(
            pair, side, quantity, fill_price,
            stop_loss, take_profit_1, take_profit_2,
            atr, setup, regime, signal_id,
        )

        self._place_protection_orders(position)
        log.info("ExecutionEngine v4.0: executed %s %.4f @ %.2f",
                 pair_side, quantity, fill_price)

        return ExecutionResult(True, order, position)

    def close_position_market(self, position_id: str) -> ExecutionResult:
        pos = self._pm.get_position(position_id)
        if not pos or pos.quantity <= 0:
            return ExecutionResult(False, error="Position not found or already closed")
        close_side = OrderSide.SELL if pos.side == OrderSide.BUY else OrderSide.BUY
        order = self._om.create_market_order(pos.pair, close_side, pos.quantity, reduce_only=True)
        if not order:
            return ExecutionResult(False, error="Close order failed")
        exit_price = order.average_fill_price if order.average_fill_price > 0 else pos.current_price
        closed = self._pm.close_position(position_id, exit_price)
        if closed:
            self._om.cancel_all_open_for_pair(pos.pair)
            log.info("ExecutionEngine v4.0: closed %s at %.2f", pos.pair, exit_price)
        return ExecutionResult(True, order, closed)

    def close_all_positions(self) -> int:
        prices = {}
        for pos in self._pm.all_positions():
            if pos.quantity > 0 and pos.pair not in prices:
                prices[pos.pair] = self._exchange.get_current_price(pos.pair)
        closed = 0
        for pos in self._pm.all_positions():
            if pos.quantity > 0:
                close_side = OrderSide.SELL if pos.side == OrderSide.BUY else OrderSide.BUY
                order = self._om.create_market_order(pos.pair, close_side, pos.quantity, reduce_only=True)
                if order:
                    self._pm.close_position(pos.id, prices.get(pos.pair, pos.current_price))
                    closed += 1
        return closed

    def revalidate_and_maybe_exit(self, position: Position, current_price: float,
                                  structure_broken: bool = False,
                                  regime_changed: bool = False,
                                  bos_contrario: bool = False,
                                  choch_contrario: bool = False) -> Optional[ExecutionResult]:
        decision = self._monitor.continuous_revalidation(
            position, current_price, structure_broken,
            regime_changed, bos_contrario, choch_contrario,
        )
        if decision == "exit":
            log.warning("ExecutionEngine v4.0: Revalidação forçou saída de %s",
                        position.pair)
            return self.close_position_market(position.id)
        return None

    def _place_protection_orders(self, position: Position) -> None:
        sl_side = OrderSide.SELL if position.side == OrderSide.BUY else OrderSide.BUY
        self._om.create_stop_order(position.pair, sl_side, position.quantity,
                                   position.stop_loss, reduce_only=True)

    def _estimate_spread(self, pair: str) -> float:
        if self._config.dry_run:
            return 0.0001
        try:
            bid, ask, _ = self._exchange.api.get_ticker_book(pair)
            if bid > 0 and ask > 0:
                return (ask - bid) / bid
        except Exception:
            pass
        return 0.001
