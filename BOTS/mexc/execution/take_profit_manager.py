import logging
from typing import Tuple

from ..bot_config import BotConfig
from ..bot_types import OrderSide, Position
from ..trading.order_manager import OrderManager

log = logging.getLogger(__name__)


class TakeProfitManager:
    def __init__(self, config: BotConfig, order_manager: OrderManager):
        self._config = config
        self._om = order_manager

    def check_take_profit(self, position: Position, current_price: float) -> Tuple[bool, float]:
        if position.quantity <= 0:
            return False, 0.0

        # For partial take profit tracking, we can check pyramiding index or direct triggers
        # If take profit level 1 hit and not yet triggered
        if position.side == OrderSide.BUY:
            if current_price >= position.take_profit_2:
                log.info("TakeProfitManager: TP2 hit on LONG %s at %.2f", position.pair, current_price)
                return True, 1.0  # 100% exit
            if current_price >= position.take_profit_1 and position.pyramiding_index == 0:
                log.info("TakeProfitManager: TP1 hit on LONG %s at %.2f", position.pair, current_price)
                position.pyramiding_index = 1
                return True, self._config.partial_tp1_pct
        else:
            if current_price <= position.take_profit_2:
                log.info("TakeProfitManager: TP2 hit on SHORT %s at %.2f", position.pair, current_price)
                return True, 1.0
            if current_price <= position.take_profit_1 and position.pyramiding_index == 0:
                log.info("TakeProfitManager: TP1 hit on SHORT %s at %.2f", position.pair, current_price)
                position.pyramiding_index = 1
                return True, self._config.partial_tp1_pct

        return False, 0.0
