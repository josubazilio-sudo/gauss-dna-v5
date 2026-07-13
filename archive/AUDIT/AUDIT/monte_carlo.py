import logging
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .backtest_audit import TradeRecord

log = logging.getLogger(__name__)


@dataclass
class MonteCarloResult:
    simulations: int = 0
    mean_return: float = 0.0
    median_return: float = 0.0
    std_return: float = 0.0
    var_95: float = 0.0
    var_99: float = 0.0
    probability_positive: float = 0.0
    probability_profit_factor_gt_1: float = 0.0
    probability_max_dd_lt_10: float = 0.0
    probability_max_dd_lt_20: float = 0.0
    expected_drawdown: float = 0.0
    expected_profit: float = 0.0
    best_return: float = 0.0
    worst_return: float = 0.0
    ruin_risk: float = 0.0
    worst_loss_streak: int = 0
    best_win_streak: int = 0
    distribution: List[float] = field(default_factory=list)
    drawdown_distribution: List[float] = field(default_factory=list)
    confidence_score: float = 0.0


class MonteCarloEngine:
    def __init__(self, num_simulations: int = 5000):
        self._num_simulations = num_simulations

    def simulate(self, trades: List[TradeRecord],
                 initial_capital: float = 10000.0,
                 position_size_pct: float = 0.02) -> MonteCarloResult:
        if not trades:
            return MonteCarloResult()

        pnls = [t.profit_loss_pct for t in trades]
        n = len(pnls)

        final_returns: List[float] = []
        drawdowns: List[float] = []
        profit_factors: List[float] = []
        loss_streaks: List[int] = []
        win_streaks: List[int] = []

        for _ in range(self._num_simulations):
            sim_capital = initial_capital
            peak = initial_capital
            max_dd = 0.0
            gross_profit = 0.0
            gross_loss = 0.0
            current_loss_streak = 0
            max_loss_streak = 0
            current_win_streak = 0
            max_win_streak = 0

            for _ in range(n):
                pnl = random.choice(pnls)
                sim_capital += sim_capital * pnl * position_size_pct
                if sim_capital > peak:
                    peak = sim_capital
                dd = (peak - sim_capital) / peak if peak > 0 else 0
                if dd > max_dd:
                    max_dd = dd
                if pnl > 0:
                    gross_profit += abs(pnl) * sim_capital * position_size_pct
                    current_loss_streak = 0
                    current_win_streak += 1
                    if current_win_streak > max_win_streak:
                        max_win_streak = current_win_streak
                else:
                    gross_loss += abs(pnl) * sim_capital * position_size_pct
                    current_win_streak = 0
                    current_loss_streak += 1
                    if current_loss_streak > max_loss_streak:
                        max_loss_streak = current_loss_streak

            final_returns.append(sim_capital)
            drawdowns.append(max_dd)
            profit_factors.append(gross_profit / gross_loss if gross_loss > 0 else 999.0)
            loss_streaks.append(max_loss_streak)
            win_streaks.append(max_win_streak)

        final_returns.sort()
        drawdowns.sort()

        mean_ret = sum(final_returns) / len(final_returns)
        sorted_rets = sorted(final_returns)
        median_ret = sorted_rets[len(sorted_rets) // 2]
        var_95 = sorted_rets[int(len(sorted_rets) * 0.05)]
        var_99 = sorted_rets[int(len(sorted_rets) * 0.01)]
        std_ret = (sum((r - mean_ret) ** 2 for r in final_returns) / len(final_returns)) ** 0.5

        positive = sum(1 for r in final_returns if r > initial_capital) / len(final_returns)
        pf_gt_1 = sum(1 for pf in profit_factors if pf >= 1.0) / len(profit_factors)
        dd_lt_10 = sum(1 for dd in drawdowns if dd <= 0.10) / len(drawdowns)
        dd_lt_20 = sum(1 for dd in drawdowns if dd <= 0.20) / len(drawdowns)
        ruin = sum(1 for r in final_returns if r <= initial_capital * 0.5) / len(final_returns)

        avg_dd = sum(drawdowns) / len(drawdowns)
        avg_pf = sum(profit_factors) / len(profit_factors)

        avg_loss_streak = sum(loss_streaks) / len(loss_streaks)
        avg_win_streak = sum(win_streaks) / len(win_streaks)

        confidence = (positive + pf_gt_1 + dd_lt_10) / 3.0 if positive > 0.7 and pf_gt_1 > 0.7 and dd_lt_10 > 0.7 else 0.0

        return MonteCarloResult(
            simulations=self._num_simulations,
            mean_return=round(mean_ret, 2),
            median_return=round(median_ret, 2),
            std_return=round(std_ret, 2),
            var_95=round(var_95, 2),
            var_99=round(var_99, 2),
            probability_positive=round(positive, 4),
            probability_profit_factor_gt_1=round(pf_gt_1, 4),
            probability_max_dd_lt_10=round(dd_lt_10, 4),
            probability_max_dd_lt_20=round(dd_lt_20, 4),
            expected_drawdown=round(avg_dd, 4),
            expected_profit=round(mean_ret - initial_capital, 2),
            best_return=round(final_returns[-1], 2),
            worst_return=round(final_returns[0], 2),
            ruin_risk=round(ruin, 4),
            worst_loss_streak=round(avg_loss_streak),
            best_win_streak=round(avg_win_streak),
            distribution=final_returns,
            drawdown_distribution=drawdowns,
            confidence_score=round(confidence, 4),
        )
