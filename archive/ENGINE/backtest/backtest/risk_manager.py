import logging
from typing import List, Optional

from .backtest_types import Trade, TradeDirection, BacktestConfig

log = logging.getLogger(__name__)


class RiskManager:
    def __init__(self, config: BacktestConfig):
        self._config = config

    def position_size(self, capital: float, price: float, atr: float) -> float:
        risk_capital = capital * self._config.position_size_pct
        if self._config.use_atr_stop and atr > 0:
            stop_distance = atr * self._config.atr_stop_multiplier
            risk_per_unit = stop_distance * risk_capital / (price * self._config.position_size_pct) if price > 0 else 0
        else:
            risk_per_unit = price * 0.02
        quantity = risk_capital / price if price > 0 else 0
        return round(quantity, 6)

    def max_drawdown_check(self, equity_curve: List[float], max_dd_pct: float) -> bool:
        if len(equity_curve) < 2:
            return True
        peak = equity_curve[0]
        for val in equity_curve:
            if val > peak:
                peak = val
            dd = (peak - val) / peak if peak > 0 else 0
            if dd > max_dd_pct:
                return False
        return True

    def kelly_criterion(self, win_rate: float, avg_win: float, avg_loss: float) -> float:
        if avg_loss == 0:
            return 0.0
        r = avg_win / avg_loss if avg_loss > 0 else 0
        kelly = win_rate - (1 - win_rate) / r if r > 0 else 0
        return max(0.0, min(kelly, 1.0))

    def daily_loss_limit_check(self, daily_pnl: float, daily_limit: float) -> bool:
        return abs(daily_pnl) <= daily_limit

    def position_sizing_kelly(self, capital: float, win_rate: float,
                               avg_win: float, avg_loss: float) -> float:
        kelly = self.kelly_criterion(win_rate, avg_win, avg_loss)
        fraction = kelly * 0.25
        return capital * fraction
