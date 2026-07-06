import logging
from typing import Any, Tuple

from ..bot_config import BotConfig
from ..bot_types import OrderSide, Position
from ..trading.order_manager import OrderManager

log = logging.getLogger(__name__)


class TakeProfitManager:
    def __init__(self, config: BotConfig, order_manager: OrderManager):
        self._config = config
        self._om = order_manager

    def validate_targets(self, position: Position, signal_score: float,
                         market_ctx: Any) -> Tuple[bool, str]:
        if position.quantity <= 0:
            return False, "Position already closed"

        tp1_rr = self._calculate_rr(position, position.take_profit_1)
        if tp1_rr < self._config.min_risk_reward:
            return False, f"RR tp1 {tp1_rr:.2f} < min {self._config.min_risk_reward}"

        if position.atr_at_entry > 0:
            if position.side == OrderSide.BUY:
                tp1_distance = position.take_profit_1 - position.entry_price
            else:
                tp1_distance = position.entry_price - position.take_profit_1
            expected_bars = tp1_distance / position.atr_at_entry
            if expected_bars > 48:
                return False, f"TP1 exige ~{expected_bars:.0f} candles — irrealista"

        if market_ctx and hasattr(market_ctx, "indicators"):
            ema = market_ctx.indicators.ema200
            if position.side == OrderSide.BUY:
                if ema > position.entry_price and ema < position.take_profit_1:
                    return False, "Resistência EMA200 antes do TP1"
            else:
                if ema < position.entry_price and ema > position.take_profit_1:
                    return False, "Suporte EMA200 antes do TP1"

        return True, "TP targets valid"

    def check_take_profit(self, position: Position, current_price: float) -> Tuple[bool, float]:
        if position.quantity <= 0:
            return False, 0.0

        if position.side == OrderSide.BUY:
            if current_price >= position.take_profit_2:
                log.info("TakeProfitManager v4.0: TP2 hit on LONG %s at %.2f",
                         position.pair, current_price)
                return True, 1.0
            if current_price >= position.take_profit_1 and position.pyramiding_index == 0:
                log.info("TakeProfitManager v4.0: TP1 hit on LONG %s at %.2f",
                         position.pair, current_price)
                position.pyramiding_index = 1
                return True, self._config.partial_tp1_pct
        else:
            if current_price <= position.take_profit_2:
                log.info("TakeProfitManager v4.0: TP2 hit on SHORT %s at %.2f",
                         position.pair, current_price)
                return True, 1.0
            if current_price <= position.take_profit_1 and position.pyramiding_index == 0:
                log.info("TakeProfitManager v4.0: TP1 hit on SHORT %s at %.2f",
                         position.pair, current_price)
                position.pyramiding_index = 1
                return True, self._config.partial_tp1_pct

        return False, 0.0

    def _calculate_rr(self, position: Position, target: float) -> float:
        if position.side == OrderSide.BUY:
            potential = target - position.entry_price
            risk = position.entry_price - position.stop_loss
        else:
            potential = position.entry_price - target
            risk = position.stop_loss - position.entry_price
        if risk <= 0:
            return 0.0
        return potential / risk
