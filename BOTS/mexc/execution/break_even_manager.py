import logging

from ..bot_config import BotConfig
from ..bot_types import OrderSide, Position
from .stop_manager import StopManager

log = logging.getLogger(__name__)


class BreakEvenManager:
    def __init__(self, config: BotConfig, stop_manager: StopManager):
        self._config = config
        self._sm = stop_manager

    def check_and_apply_break_even(self, position: Position, current_price: float) -> bool:
        if position.quantity <= 0 or position.break_even_activated:
            return False

        # Calculate gain percentage
        if position.side == OrderSide.BUY:
            gain_pct = (current_price - position.entry_price) / position.entry_price
        else:
            gain_pct = (position.entry_price - current_price) / position.entry_price

        if gain_pct >= self._config.break_even_activation_pct:
            log.info("BreakEvenManager: break even activated for %s @ %.2f", position.pair, current_price)
            position.break_even_activated = True
            # Set stop loss to entry price plus a tiny buffer for fees
            self._sm.update_stop_loss(position, position.entry_price)
            return True

        return False
