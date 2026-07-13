import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from ..bot_config import BotConfig
from ..bot_types import Order, OrderSide, OrderStatus, OrderType, TimeInForce
from ..exchange.connector import ExchangeConnector
from CORE.execution.mode_manager import ExecutionModeManager

log = logging.getLogger(__name__)


class OrderManager:
    def __init__(self, config: BotConfig, exchange: ExchangeConnector):
        self._config = config
        self._exchange = exchange
        self._orders: Dict[str, Order] = {}
        self._pending_cancels: set = set()

    def _should_dry_run(self) -> bool:
        """Gate de seguranca: uma ordem so pode ser real se dry_run=False
        E o modo de execucao ativo for LIVE. Qualquer dessincronia entre
        BotConfig.dry_run e QUANTOS_MODE forca DRY RUN por seguranca."""
        if self._should_dry_run():
            return True
        if not ExecutionModeManager().can_trade():
            log.error(
                "OrderManager: dry_run=False mas modo de execucao (%s) nao permite ordens reais "
                "— forcando DRY RUN por seguranca",
                ExecutionModeManager().mode_name,
            )
            return True
        return False

    def all_orders(self) -> List[Order]:
        return list(self._orders.values())

    def get_order(self, order_id: str) -> Optional[Order]:
        return self._orders.get(order_id)

    def get_orders_by_pair(self, pair: str) -> List[Order]:
        return [o for o in self._orders.values() if o.pair == pair]

    def get_open_orders(self) -> List[Order]:
        return [o for o in self._orders.values() if o.is_open()]

    def get_open_orders_by_pair(self, pair: str) -> List[Order]:
        return [o for o in self._orders.values() if o.pair == pair and o.is_open()]

    def create_market_order(self, pair: str, side: OrderSide, quantity: float,
                            signal_id: Optional[str] = None, reduce_only: bool = False,
                            entry_price: float = 0.0) -> Optional[Order]:
        order_id = self._generate_id()
        order = Order(
            id=order_id,
            exchange_id="",
            pair=pair,
            side=side,
            order_type=OrderType.MARKET,
            quantity=quantity,
            price=0.0,
            status=OrderStatus.PENDING,
            signal_id=signal_id,
            reduce_only=reduce_only,
        )
        if self._should_dry_run():
            order.status = OrderStatus.FILLED
            order.filled_quantity = quantity
            order.average_fill_price = entry_price if entry_price > 0 else self._get_mock_price(pair)
            self._orders[order_id] = order
            log.info("OrderManager: DRY RUN market %s %s %s", side.value, quantity, pair)
            return order
        result = self._exchange.create_market_order(pair, side, quantity, reduce_only)
        if result:
            order.exchange_id = result.exchange_id
            order.status = OrderStatus.OPEN
            self._orders[order_id] = order
        return order

    def create_limit_order(self, pair: str, side: OrderSide, quantity: float, price: float,
                            tif: TimeInForce = TimeInForce.GTC, signal_id: Optional[str] = None,
                            reduce_only: bool = False) -> Optional[Order]:
        order_id = self._generate_id()
        order = Order(
            id=order_id,
            exchange_id="",
            pair=pair,
            side=side,
            order_type=OrderType.LIMIT,
            quantity=quantity,
            price=price,
            status=OrderStatus.PENDING,
            signal_id=signal_id,
            time_in_force=tif,
            reduce_only=reduce_only,
        )
        if self._should_dry_run():
            order.status = OrderStatus.FILLED
            order.filled_quantity = quantity
            order.average_fill_price = price
            self._orders[order_id] = order
            log.info("OrderManager: DRY RUN limit %s %s %s @ %.2f", side.value, quantity, pair, price)
            return order
        result = self._exchange.create_limit_order(pair, side, quantity, price, tif, reduce_only)
        if result:
            order.exchange_id = result.exchange_id
            order.status = OrderStatus.OPEN
            self._orders[order_id] = order
        return order

    def create_stop_order(self, pair: str, side: OrderSide, quantity: float,
                           stop_price: float, signal_id: Optional[str] = None,
                           reduce_only: bool = True) -> Optional[Order]:
        order_id = self._generate_id()
        order = Order(
            id=order_id,
            exchange_id="",
            pair=pair,
            side=side,
            order_type=OrderType.STOP,
            quantity=quantity,
            price=0.0,
            stop_price=stop_price,
            status=OrderStatus.PENDING,
            signal_id=signal_id,
            reduce_only=reduce_only,
        )
        if self._should_dry_run():
            order.status = OrderStatus.OPEN
            self._orders[order_id] = order
            log.info("OrderManager: DRY RUN stop %s %s %s @ %.2f", side.value, quantity, pair, stop_price)
            return order
        result = self._exchange.create_stop_order(pair, side, quantity, stop_price, reduce_only)
        if result:
            order.exchange_id = result.exchange_id
            order.status = OrderStatus.OPEN
            self._orders[order_id] = order
        return order

    def cancel_order(self, order_id: str) -> bool:
        order = self._orders.get(order_id)
        if not order or order.status in (OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED):
            return False
        if self._should_dry_run():
            order.status = OrderStatus.CANCELLED
            order.updated_at = datetime.now(timezone.utc)
            log.info("OrderManager: DRY RUN cancelled %s", order_id)
            return True
        self._pending_cancels.add(order_id)
        success = self._exchange.cancel_order(order.pair, order.exchange_id)
        if success:
            order.status = OrderStatus.CANCELLED
            order.updated_at = datetime.now(timezone.utc)
        self._pending_cancels.discard(order_id)
        return success

    def update_order_status(self, order_id: str, status: OrderStatus, filled_qty: float = 0.0,
                             fill_price: float = 0.0) -> None:
        order = self._orders.get(order_id)
        if not order:
            return
        order.status = status
        order.updated_at = datetime.now(timezone.utc)
        if filled_qty > 0:
            order.filled_quantity = filled_qty
            order.filled_amount += filled_qty * fill_price
            order.average_fill_price = fill_price

    def remove_order(self, order_id: str) -> None:
        self._orders.pop(order_id, None)

    def clear_filled(self) -> None:
        to_remove = [oid for oid, o in self._orders.items() if o.status in (
            OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.EXPIRED)]
        for oid in to_remove:
            self._orders.pop(oid, None)

    def sync_open_orders(self) -> None:
        for order in self.get_open_orders():
            if self._should_dry_run():
                continue
            status_data = self._exchange.get_order_status(order.pair, order.exchange_id)
            if status_data:
                status = self._map_status(status_data.get("status", ""))
                order.status = status
                order.updated_at = datetime.now(timezone.utc)
                if "executedQty" in status_data:
                    order.filled_quantity = float(status_data["executedQty"])
                if "cummulativeQuoteQty" in status_data:
                    order.filled_amount = float(status_data["cummulativeQuoteQty"])

    def cancel_all_open(self) -> int:
        cancelled = 0
        for order in self.get_open_orders():
            if self.cancel_order(order.id):
                cancelled += 1
        return cancelled

    def cancel_all_open_for_pair(self, pair: str) -> int:
        cancelled = 0
        for order in self.get_open_orders_by_pair(pair):
            if self.cancel_order(order.id):
                cancelled += 1
        return cancelled

    def _generate_id(self) -> str:
        return f"mexc_{uuid.uuid4().hex[:16]}"

    def _get_mock_price(self, pair: str) -> float:
        prices = {"BTCUSDT": 65000.0, "ETHUSDT": 3500.0, "SOLUSDT": 145.0}
        return prices.get(pair, 100.0)

    def _map_status(self, status: str) -> OrderStatus:
        mapping = {
            "NEW": OrderStatus.OPEN,
            "OPEN": OrderStatus.OPEN,
            "PARTIALLY_FILLED": OrderStatus.PARTIALLY_FILLED,
            "FILLED": OrderStatus.FILLED,
            "CANCELED": OrderStatus.CANCELLED,
            "CANCELLED": OrderStatus.CANCELLED,
            "REJECTED": OrderStatus.REJECTED,
            "EXPIRED": OrderStatus.EXPIRED,
        }
        return mapping.get(status.upper(), OrderStatus.PENDING)
