import logging
import random
from typing import List, Tuple, Callable

from .backtest_types import Trade, WalkForwardResult, BacktestResult
from .backtest_config import WALK_FORWARD_WINDOWS, WALK_FORWARD_TRAIN_PCT
from .statistics_engine import compute_statistics

log = logging.getLogger(__name__)


def walk_forward(
    trades: List[Trade],
    equity_curve: List[float],
    initial_capital: float,
    final_capital: float,
    windows: int = WALK_FORWARD_WINDOWS,
) -> WalkForwardResult:
    if len(trades) < windows * 10:
        return WalkForwardResult()

    chunk_size = len(trades) // windows
    results = []

    for w in range(windows):
        train_start = 0
        train_end = int((w + 1) * chunk_size * WALK_FORWARD_TRAIN_PCT)
        test_start = train_end
        test_end = min(len(trades), (w + 1) * chunk_size)

        if test_end <= test_start or test_start >= len(trades):
            continue

        train_trades = trades[train_start:train_end]
        test_trades = trades[test_start:test_end]

        if len(train_trades) < 5 or len(test_trades) < 3:
            continue

        train_result = compute_statistics(train_trades, [], initial_capital, 0)
        test_result = compute_statistics(test_trades, [], initial_capital, 0)

        in_score = _score_result(train_result)
        out_score = _score_result(test_result)

        results.append({
            "window": w,
            "in_sample_score": in_score,
            "out_sample_score": out_score,
            "train_trades": len(train_trades),
            "test_trades": len(test_trades),
        })

    if not results:
        return WalkForwardResult()

    in_scores = [r["in_sample_score"] for r in results]
    out_scores = [r["out_sample_score"] for r in results]
    avg_in = sum(in_scores) / len(in_scores)
    avg_out = sum(out_scores) / len(out_scores)

    stability = 1.0 - (max(out_scores) - min(out_scores)) if out_scores else 0.0
    stability = max(0.0, min(stability, 1.0))

    wfa = avg_out / avg_in if avg_in > 0 else 0.0

    return WalkForwardResult(
        in_sample_score=round(avg_in, 4),
        out_sample_score=round(avg_out, 4),
        wfa_score=round(min(wfa, 1.0), 4),
        parameter_stability=round(stability, 4),
        windows=results,
    )


def _score_result(result: BacktestResult) -> float:
    wr = min(result.win_rate / 0.6, 1.0) * 0.25 if result.win_rate > 0 else 0
    pf = min(result.profit_factor / 2.5, 1.0) * 0.30 if result.profit_factor > 0 else 0
    dd = max(0, 1.0 - (result.max_drawdown_pct / 0.15)) * 0.25
    exp = min(abs(result.expectancy) / 50, 1.0) * 0.20 if result.expectancy > 0 else 0
    return wr + pf + dd + exp
