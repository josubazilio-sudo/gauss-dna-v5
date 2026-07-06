import logging
from typing import List, Optional, Tuple

from .backtest_types import (
    Trade, TradeDirection, TradeStatus, ExitReason, BacktestConfig,
)

log = logging.getLogger(__name__)


class PositionManager:
    def __init__(self, config: BacktestConfig):
        self._config = config
        self._positions: List[Trade] = []

    def open_positions(self) -> List[Trade]:
        return [t for t in self._positions if t.status == TradeStatus.OPEN]

    def all_trades(self) -> List[Trade]:
        return list(self._positions)

    def can_open(self) -> bool:
        open_count = len(self.open_positions())
        if self._config.pyramiding:
            return open_count < self._config.pyramiding_levels
        return open_count < self._config.max_positions

    def add_trade(self, trade: Trade) -> None:
        self._positions.append(trade)

    def update_positions(self, high: float, low: float, close: float,
                         current_time: datetime) -> List[Trade]:
        closed: List[Trade] = []
        for trade in self.open_positions():
            result = self._check_exit(trade, high, low, close, current_time)
            if result is not None:
                exit_price, reason = result
                from .trade_simulator import close_trade
                closed.append(close_trade(trade, exit_price, current_time, reason, self._config))
        return closed

    def _check_exit(self, trade: Trade, high: float, low: float,
                    close: float, current_time: datetime) -> Optional[Tuple[float, ExitReason]]:
        if trade.status != TradeStatus.OPEN:
            return None

        if trade.direction == TradeDirection.LONG:
            if low <= trade.stop_loss:
                return trade.stop_loss, ExitReason.STOP_LOSS
            if trade.trailing_stop_activated:
                new_sl = max(trade.stop_loss, high * (1 - self._config.trailing_stop_distance))
                if new_sl > trade.stop_loss:
                    trade.stop_loss = new_sl
                if low <= trade.stop_loss:
                    return trade.stop_loss, ExitReason.TRAILING_STOP
            if trade.break_even_activated:
                if high >= trade.entry_price and trade.stop_loss < trade.entry_price:
                    trade.stop_loss = trade.entry_price
            if self._config.trailing_stop_activation > 0 and not trade.trailing_stop_activated:
                gain_pct = (high - trade.entry_price) / trade.entry_price
                if gain_pct >= self._config.trailing_stop_activation:
                    trade.trailing_stop_activated = True
                    trade.stop_loss = high * (1 - self._config.trailing_stop_distance)
            if self._config.break_even_activation > 0 and not trade.break_even_activated:
                gain_pct = (high - trade.entry_price) / trade.entry_price
                if gain_pct >= self._config.break_even_activation:
                    trade.break_even_activated = True
            if high >= trade.take_profit_2:
                tp2_qty = trade.quantity * (1 - self._config.partial_tp1_pct) if self._config.partial_tp1_pct < 1.0 else trade.quantity
                if tp2_qty == trade.quantity or self._config.partial_tp1_pct >= 1.0:
                    return trade.take_profit_2, ExitReason.TAKE_PROFIT_2
            if high >= trade.take_profit_1:
                return trade.take_profit_1, ExitReason.TAKE_PROFIT_1

        else:
            if high >= trade.stop_loss:
                return trade.stop_loss, ExitReason.STOP_LOSS
            if trade.trailing_stop_activated:
                new_sl = min(trade.stop_loss, low * (1 + self._config.trailing_stop_distance))
                if new_sl < trade.stop_loss:
                    trade.stop_loss = new_sl
                if high >= trade.stop_loss:
                    return trade.stop_loss, ExitReason.TRAILING_STOP
            if trade.break_even_activated:
                if low <= trade.entry_price and trade.stop_loss > trade.entry_price:
                    trade.stop_loss = trade.entry_price
            if self._config.trailing_stop_activation > 0 and not trade.trailing_stop_activated:
                gain_pct = (trade.entry_price - low) / trade.entry_price
                if gain_pct >= self._config.trailing_stop_activation:
                    trade.trailing_stop_activated = True
                    trade.stop_loss = low * (1 + self._config.trailing_stop_distance)
            if self._config.break_even_activation > 0 and not trade.break_even_activated:
                gain_pct = (trade.entry_price - low) / trade.entry_price
                if gain_pct >= self._config.break_even_activation:
                    trade.break_even_activated = True
            if low <= trade.take_profit_2:
                tp2_qty = trade.quantity * (1 - self._config.partial_tp1_pct) if self._config.partial_tp1_pct < 1.0 else trade.quantity
                if tp2_qty == trade.quantity or self._config.partial_tp1_pct >= 1.0:
                    return trade.take_profit_2, ExitReason.TAKE_PROFIT_2
            if low <= trade.take_profit_1:
                return trade.take_profit_1, ExitReason.TAKE_PROFIT_1

        if self._config.max_bars_hold > 0:
            trade.holding_bars += 1
            if trade.holding_bars >= self._config.max_bars_hold:
                return close, ExitReason.TIME_EXPIRY

        return None

    def reset(self) -> None:
        self._positions.clear()
