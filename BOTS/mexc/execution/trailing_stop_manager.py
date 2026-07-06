import logging

from ..bot_config import BotConfig
from ..bot_types import OrderSide, Position
from .stop_manager import StopManager

log = logging.getLogger(__name__)


class TrailingStopManager:
    def __init__(self, config: BotConfig, stop_manager: StopManager):
        self._config = config
        self._sm = stop_manager

    def check_and_apply_trailing_stop(self, position: Position, current_price: float) -> bool:
        if position.quantity <= 0:
            return False

        if position.side == OrderSide.BUY:
            gain_pct = (current_price - position.entry_price) / position.entry_price
        else:
            gain_pct = (position.entry_price - current_price) / position.entry_price

        # Check if trailing stop is activated
        if not position.trailing_stop_activated:
            if gain_pct >= self._config.trailing_stop_activation_pct:
                log.info("TrailingStopManager: trailing stop activated for %s @ %.2f", position.pair, current_price)
                position.trailing_stop_activated = True
            else:
                return False

        # If activated, calculate trailing SL
        if position.side == OrderSide.BUY:
            target_sl = current_price * (1 - self._config.trailing_stop_distance_pct)
            if target_sl > position.stop_loss:
                self._sm.update_stop_loss(position, target_sl)
                return True
        else:
            target_sl = current_price * (1 + self._config.trailing_stop_distance_pct)
            if target_sl < position.stop_loss:
                self._sm.update_stop_loss(position, target_sl)
                return True

        return False
