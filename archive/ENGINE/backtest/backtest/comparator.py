import logging
from typing import Dict, List

from .backtest_types import BacktestResult, ComparisonResult

log = logging.getLogger(__name__)


def compare_strategies(
    results: Dict[str, BacktestResult],
) -> List[ComparisonResult]:
    comparisons = []
    names = list(results.keys())
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            delta = _compute_deltas(results[a], results[b])
            better = a if delta.get("composite", 0) > 0 else b
            comparisons.append(ComparisonResult(
                strategy_a=a,
                strategy_b=b,
                metric_deltas=delta,
                better_strategy=better,
                significance=abs(delta.get("composite", 0)),
            ))
    return comparisons


def compare_versions(
    version_a: str,
    version_b: str,
    result_a: BacktestResult,
    result_b: BacktestResult,
) -> ComparisonResult:
    deltas = _compute_deltas(result_a, result_b)
    better = version_a if deltas.get("composite", 0) > 0 else version_b
    return ComparisonResult(
        strategy_a=version_a,
        strategy_b=version_b,
        metric_deltas=deltas,
        better_strategy=better,
        significance=abs(deltas.get("composite", 0)),
    )


def _compute_deltas(a: BacktestResult, b: BacktestResult) -> Dict[str, float]:
    return {
        "win_rate": round(a.win_rate - b.win_rate, 4),
        "profit_factor": round(a.profit_factor - b.profit_factor, 4),
        "net_profit": round(a.net_profit - b.net_profit, 4),
        "max_drawdown_pct": round(b.max_drawdown_pct - a.max_drawdown_pct, 4),
        "sharpe_ratio": round(a.sharpe_ratio - b.sharpe_ratio, 4),
        "expectancy": round(a.expectancy - b.expectancy, 4),
        "composite": round(
            (a.win_rate - b.win_rate) * 0.15 +
            (a.profit_factor - b.profit_factor) * 0.25 +
            (a.net_profit - b.net_profit) * 0.20 +
            (b.max_drawdown_pct - a.max_drawdown_pct) * 0.20 +
            (a.sharpe_ratio - b.sharpe_ratio) * 0.10 +
            (a.expectancy - b.expectancy) * 0.10, 4
        ),
    }
