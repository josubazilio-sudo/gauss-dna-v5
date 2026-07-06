import logging
import itertools
import random
from typing import Dict, List, Optional, Callable, Tuple

from .backtest_types import BacktestResult, OptimizationParam, OptimizationResult
from .backtest_config import OPTIMIZATION_DEFAULT_RUNS

log = logging.getLogger(__name__)


class ParameterOptimizer:
    def __init__(self, objective_fn: Callable[..., BacktestResult]):
        self._objective = objective_fn

    def grid_search(self, params: List[OptimizationParam]) -> OptimizationResult:
        best_score = -float("inf")
        best_params = {}
        best_result = None
        total = 0

        ranges = [self._expand(p) for p in params]
        for combination in itertools.product(*ranges):
            param_dict = {params[i].name: combination[i] for i in range(len(params))}
            try:
                result = self._objective(**param_dict)
                score = self._score(result)
                if score > best_score:
                    best_score = score
                    best_params = param_dict
                    best_result = result
                total += 1
            except Exception as e:
                log.warning(f"Optimization run failed: {e}")

        improvements = {}
        if best_result:
            improvements = {
                "win_rate": best_result.win_rate,
                "profit_factor": best_result.profit_factor,
                "max_drawdown_pct": best_result.max_drawdown_pct,
            }

        return OptimizationResult(
            best_params=best_params,
            best_result=best_result,
            total_runs=total,
            improvements=improvements,
        )

    def random_search(self, params: List[OptimizationParam],
                       runs: int = OPTIMIZATION_DEFAULT_RUNS) -> OptimizationResult:
        best_score = -float("inf")
        best_params = {}
        best_result = None

        for _ in range(runs):
            param_dict = {}
            for p in params:
                values = self._expand(p)
                param_dict[p.name] = random.choice(values)
            try:
                result = self._objective(**param_dict)
                score = self._score(result)
                if score > best_score:
                    best_score = score
                    best_params = param_dict
                    best_result = result
            except Exception as e:
                log.warning(f"Optimization run failed: {e}")

        improvements = {}
        if best_result:
            improvements = {
                "win_rate": best_result.win_rate,
                "profit_factor": best_result.profit_factor,
                "max_drawdown_pct": best_result.max_drawdown_pct,
            }

        return OptimizationResult(
            best_params=best_params,
            best_result=best_result,
            total_runs=runs,
            improvements=improvements,
        )

    def _expand(self, param: OptimizationParam) -> List[float]:
        values = []
        v = param.min_val
        while v <= param.max_val + param.step * 0.5:
            values.append(round(v, 6))
            v += param.step
        return values

    def _score(self, result: BacktestResult) -> float:
        wr = min(result.win_rate / 0.6, 1.0) * 0.20
        pf = min(result.profit_factor / 2.5, 1.0) * 0.30
        dd = max(0.0, 1.0 - result.max_drawdown_pct / 0.15) * 0.25
        exp = min(abs(result.expectancy) / 50, 1.0) * 0.15 if result.expectancy > 0 else 0
        trades = min(result.total_trades / 100, 1.0) * 0.10
        return wr + pf + dd + exp + trades
