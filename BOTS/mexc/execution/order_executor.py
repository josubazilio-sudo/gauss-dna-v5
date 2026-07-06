import logging
from typing import Optional

from ..bot_config import BotConfig
from ..bot_types import Order, OrderSide, Position
from ..trading.order_manager import OrderManager
from ..trading.position_manager import BotPositionManager

log = logging.getLogger(__name__)


class OrderExecutor:
    def __init__(self, config: BotConfig, order_manager: OrderManager, position_manager: BotPositionManager):
        self._config = config
        self._om = order_manager
        self._pm = position_manager

    def place_order(self, pair: str, side: OrderSide, quantity: float, price: float = 0.0,
                    stop_price: float = 0.0, is_stop: bool = False, is_limit: bool = False,
                    reduce_only: bool = False) -> Optional[Order]:
        if is_stop:
            if is_limit:
                return self._om.create_stop_limit_order(pair, side, quantity, stop_price, price, reduce_only)
            return self._om.create_stop_order(pair, side, quantity, stop_price, reduce_only)
        elif is_limit:
            return self._om.create_limit_order(pair, side, quantity, price, reduce_only=reduce_only)
        return self._om.create_market_order(pair, side, quantity, reduce_only=reduce_only)

    def cancel_order(self, order_id: str) -> bool:
        return self._om.cancel_order(order_id)
