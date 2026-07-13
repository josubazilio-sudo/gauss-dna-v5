import logging
import math
import random
from typing import List

from .backtest_types import Trade, MonteCarloResult, BacktestResult
from .backtest_config import MONTE_CARLO_SIMULATIONS, MONTE_CARLO_CONFIDENCE

log = logging.getLogger(__name__)


class MonteCarloEngine:
    def __init__(self, simulations: int = MONTE_CARLO_SIMULATIONS):
        self._simulations = simulations

    def simulate(self, trades: List[Trade], initial_capital: float) -> MonteCarloResult:
        if not trades:
            return MonteCarloResult()

        pnl_values = [t.pnl for t in trades]
        r_multiple_values = [t.r_multiple for t in trades]

        results = []
        for _ in range(self._simulations):
            sim_pnls = [random.choice(pnl_values) for _ in range(len(trades))]
            sim_capital = initial_capital + sum(sim_pnls)
            results.append(sim_capital)

        sorted_results = sorted(results)
        mean = sum(results) / len(results)
        median = sorted_results[len(sorted_results) // 2]
        variance = sum((r - mean) ** 2 for r in results) / len(results)
        std = math.sqrt(variance)

        var_95_idx = int(len(sorted_results) * 0.05)
        var_99_idx = int(len(sorted_results) * 0.01)
        var_95 = sorted_results[var_95_idx] - initial_capital if var_95_idx < len(sorted_results) else 0.0
        var_99 = sorted_results[var_99_idx] - initial_capital if var_99_idx < len(sorted_results) else 0.0

        prob_positive = sum(1 for r in results if r > initial_capital) / len(results)

        sim_pfs = []
        for _ in range(min(self._simulations, 500)):
            sim = [random.choice(pnl_values) for _ in range(len(trades))]
            pos = sum(p for p in sim if p > 0)
            neg = abs(sum(p for p in sim if p < 0))
            sim_pfs.append(pos / neg if neg > 0 else 10.0)
        prob_pf_gt_1 = sum(1 for pf in sim_pfs if pf > 1.0) / len(sim_pfs)

        initial = initial_capital
        prob_dd_lt_10 = 0.0
        dd_count = 0
        for _ in range(min(self._simulations, 500)):
            sim = [random.choice(pnl_values) for _ in range(len(trades))]
            curve = [initial]
            for p in sim:
                curve.append(curve[-1] + p)
            peak = curve[0]
            max_dd = 0.0
            for v in curve:
                if v > peak:
                    peak = v
                dd = (peak - v) / peak if peak > 0 else 0
                if dd > max_dd:
                    max_dd = dd
            if max_dd < 0.10:
                dd_count += 1
        prob_dd_lt_10 = dd_count / 500

        confidence = 0.0
        if prob_positive > 0.7 and prob_pf_gt_1 > 0.7 and prob_dd_lt_10 > 0.7:
            confidence = (prob_positive + prob_pf_gt_1 + prob_dd_lt_10) / 3

        return MonteCarloResult(
            mean_return=round(mean - initial_capital, 4),
            median_return=round(median - initial_capital, 4),
            std_return=round(std, 4),
            var_95=round(var_95, 4),
            var_99=round(var_99, 4),
            probability_positive=round(prob_positive, 4),
            probability_profit_factor_gt_1=round(prob_pf_gt_1, 4),
            probability_max_dd_lt_10=round(prob_dd_lt_10, 4),
            confidence_score=round(confidence, 4),
            simulations=self._simulations,
        )
