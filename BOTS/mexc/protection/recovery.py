import logging
import time
from datetime import datetime, timezone
from typing import List

from ..bot_config import BotConfig
from ..bot_types import BotStatus, ConnectionStatus, Order, OrderStatus
from ..exchange.connector import ExchangeConnector
from ..trading.order_manager import OrderManager
from ..trading.position_manager import BotPositionManager

log = logging.getLogger(__name__)


class RecoveryEngine:
    def __init__(self, config: BotConfig, exchange: ExchangeConnector,
                 order_manager: OrderManager, position_manager: BotPositionManager):
        self._config = config
        self._exchange = exchange
        self._om = order_manager
        self._pm = position_manager
        self._last_sync_time = 0.0

    def recover(self) -> bool:
        log.info("RecoveryEngine: starting recovery process...")
        try:
            # Reconnect exchange if disconnected
            if not self._exchange.is_connected:
                log.info("RecoveryEngine: exchange disconnected, attempting reconnect...")
                success = self._exchange.reconnect()
                if not success:
                    log.error("RecoveryEngine: reconnection failed")
                    return False

            # Sync open orders and cancel orphaned/duplicate orders
            self.sync_orders()

            # Sync active positions
            self.sync_positions()

            log.info("RecoveryEngine: recovery process completed successfully")
            return True
        except Exception as e:
            log.exception("RecoveryEngine: error during recovery: %s", e)
            return False

    def sync_orders(self) -> None:
        log.info("RecoveryEngine: syncing open orders...")
        self._om.sync_open_orders()

        # Check for orphan orders (orders that exist on exchange but not in order manager)
        for pair in self._config.pairs:
            if self._config.dry_run:
                continue
            try:
                ex_orders = self._exchange.get_open_orders(pair)
                local_ex_ids = {o.exchange_id for o in self._om.get_open_orders_by_pair(pair)}
                for ex_order in ex_orders:
                    ex_id = str(ex_order.get("orderId"))
                    if ex_id not in local_ex_ids:
                        log.warning("RecoveryEngine: found orphan order %s on exchange. Cancelling...", ex_id)
                        self._exchange.cancel_order(pair, ex_id)
            except Exception as e:
                log.error("RecoveryEngine: failed to sync open orders for %s: %s", pair, e)

    def sync_positions(self) -> None:
        log.info("RecoveryEngine: syncing active positions...")
        self._pm.sync_positions()

        # Check for positions without active stop orders (orphan positions)
        for pos in self._pm.all_positions():
            if pos.quantity > 0:
                open_orders = self._om.get_open_orders_by_pair(pos.pair)
                has_stop = any(o.order_type in (OrderStatus.OPEN, OrderStatus.PENDING) and o.stop_price > 0 for o in open_orders)
                if not has_stop:
                    log.warning("RecoveryEngine: found orphan position %s with no stop order. Creating stop order...", pos.pair)
                    sl_side = "sell" if pos.side == "buy" else "buy"
                    # Create a new stop order
                    from ..bot_types import OrderSide
                    side = OrderSide.SELL if pos.side == OrderSide.BUY else OrderSide.BUY
                    self._om.create_stop_order(pos.pair, side, pos.quantity, pos.stop_loss, reduce_only=True)

    def handle_disconnect(self) -> None:
        log.warning("RecoveryEngine: connection lost. Initiating automatic reconnect loop...")
        for attempt in range(self._config.reconnection_attempts):
            log.info("RecoveryEngine: reconnection attempt %d/%d...", attempt + 1, self._config.reconnection_attempts)
            if self._exchange.reconnect():
                log.info("RecoveryEngine: reconnected successfully")
                return
            time.sleep(self._config.reconnection_delay_seconds)
        log.critical("RecoveryEngine: failed to reconnect after %d attempts", self._config.reconnection_attempts)
