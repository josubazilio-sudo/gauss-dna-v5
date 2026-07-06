import logging
from typing import Optional

from ..bot_config import BotConfig
from ..bot_types import OrderSide, Position
from ..trading.order_manager import OrderManager

log = logging.getLogger(__name__)


class StopManager:
    def __init__(self, config: BotConfig, order_manager: OrderManager):
        self._config = config
        self._om = order_manager

    def check_and_adjust_stop(self, position: Position, current_price: float) -> bool:
        if position.quantity <= 0:
            return False

        if position.side == OrderSide.BUY:
            if current_price <= position.stop_loss:
                log.info("StopManager: LONG SL hit on %s at %.2f (target SL: %.2f)",
                         position.pair, current_price, position.stop_loss)
                return True
        else:
            if current_price >= position.stop_loss:
                log.info("StopManager: SHORT SL hit on %s at %.2f (target SL: %.2f)",
                         position.pair, current_price, position.stop_loss)
                return True

        return False

    def update_stop_loss(self, position: Position, new_stop_loss: float) -> None:
        if position.side == OrderSide.BUY:
            if new_stop_loss <= position.stop_loss:
                return
        else:
            if new_stop_loss >= position.stop_loss:
                return

        log.info("StopManager: adjusting SL on %s from %.2f to %.2f",
                 position.pair, position.stop_loss, new_stop_loss)
        position.stop_loss = new_stop_loss

        # Cancel previous stop order for this pair and place a new one
        self._om.cancel_all_open_for_pair(position.pair)
        sl_side = OrderSide.SELL if position.side == OrderSide.BUY else OrderSide.BUY
        self._om.create_stop_order(position.pair, sl_side, position.quantity,
                                    new_stop_loss, reduce_only=True)
