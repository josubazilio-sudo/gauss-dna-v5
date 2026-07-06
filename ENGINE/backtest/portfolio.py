import logging
from typing import Dict, List, Optional

from .backtest_types import Trade, TradeDirection, BacktestConfig, BacktestResult

log = logging.getLogger(__name__)


class PortfolioSimulator:
    def __init__(self, config: BacktestConfig):
        self._config = config
        self._results: Dict[str, BacktestResult] = {}

    def add_result(self, pair: str, result: BacktestResult) -> None:
        self._results[pair] = result

    def portfolio_result(self) -> BacktestResult:
        if not self._results:
            return BacktestResult()

        all_trades = []
        total_initial = 0.0
        total_final = 0.0

        for pair, result in self._results.items():
            all_trades.extend(result.trades)
            total_initial += result.config.initial_capital
            total_final += result.final_capital

        from .statistics_engine import compute_statistics
        combined = compute_statistics(all_trades, [], total_initial, total_final)
        combined.config = self._config
        return combined

    def correlation_matrix(self) -> Dict[str, Dict[str, float]]:
        pairs = list(self._results.keys())
        matrix: Dict[str, Dict[str, float]] = {p: {q: 0.0 for q in pairs} for p in pairs}
        for p in pairs:
            matrix[p][p] = 1.0
            for q in pairs:
                if p >= q:
                    continue
                corr = self._correlate(self._results[p].trades, self._results[q].trades)
                matrix[p][q] = corr
                matrix[q][p] = corr
        return matrix

    def _correlate(self, trades_a: List[Trade], trades_b: List[Trade]) -> float:
        min_len = min(len(trades_a), len(trades_b))
        if min_len < 5:
            return 0.0
        a = [t.pnl for t in trades_a[:min_len]]
        b = [t.pnl for t in trades_b[:min_len]]
        n = min_len
        mean_a = sum(a) / n
        mean_b = sum(b) / n
        cov = sum((ai - mean_a) * (bi - mean_b) for ai, bi in zip(a, b))
        var_a = sum((ai - mean_a) ** 2 for ai in a)
        var_b = sum((bi - mean_b) ** 2 for bi in b)
        if var_a == 0 or var_b == 0:
            return 0.0
        r = cov / ((var_a * var_b) ** 0.5)
        return round(max(-1.0, min(1.0, r)), 4)
