import statistics
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from .backtest_audit import BacktestResult, TradeRecord


class RobustnessMatrix:
    def __init__(self, result: BacktestResult):
        self._trades = result.trades

    # ------------------------------------------------------------------ #
    #  Public matrix builders
    # ------------------------------------------------------------------ #

    def asset_by_timeframe(self) -> Dict[Tuple[str, str], Dict[str, Any]]:
        return self._build_matrix(lambda t: (t.pair, t.timeframe))

    def setup_by_timeframe(self) -> Dict[Tuple[str, str], Dict[str, Any]]:
        return self._build_matrix(lambda t: (t.setup, t.timeframe))

    def setup_by_asset(self) -> Dict[Tuple[str, str], Dict[str, Any]]:
        return self._build_matrix(lambda t: (t.setup, t.pair))

    def regime_by_asset(self) -> Dict[Tuple[str, str], Dict[str, Any]]:
        return self._build_matrix(lambda t: (t.regime, t.pair))

    def regime_by_timeframe(self) -> Dict[Tuple[str, str], Dict[str, Any]]:
        return self._build_matrix(lambda t: (t.regime, t.timeframe))

    # ------------------------------------------------------------------ #
    #  Best / worst
    # ------------------------------------------------------------------ #

    def best_combinations(self, min_trades: int = 5, top_n: int = 10):
        candidates = self._flatten_all(min_trades)
        candidates.sort(key=lambda x: x[1]["profit_factor"], reverse=True)
        return candidates[:top_n]

    def worst_combinations(self, min_trades: int = 5, top_n: int = 10):
        candidates = self._flatten_all(min_trades)
        candidates.sort(key=lambda x: x[1]["profit_factor"])
        return candidates[:top_n]

    # ------------------------------------------------------------------ #
    #  Summary table
    # ------------------------------------------------------------------ #

    def summary(self, min_trades: int = 5) -> str:
        matrices = {
            "Asset x TF": self.asset_by_timeframe(),
            "Setup x TF": self.setup_by_timeframe(),
            "Setup x Asset": self.setup_by_asset(),
            "Regime x Asset": self.regime_by_asset(),
            "Regime x TF": self.regime_by_timeframe(),
        }

        lines = ["=== ROBUSTNESS MATRIX SUMMARY ===", ""]
        sep = "-" * 100

        for title, matrix in matrices.items():
            lines.append(f"  {title}")
            lines.append(sep)
            header = f"  {'Row':<20} {'Col':<12} {'Trades':>7} {'WR':>7} {'PF':>8} {'Sharpe':>8} {'DD':>8} {'AvgRR':>7}"
            lines.append(header)
            lines.append(sep)

            # sort by profit_factor descending, filter min_trades
            items = sorted(
                ((k, v) for k, v in matrix.items() if v["trades"] >= min_trades),
                key=lambda x: x[1]["profit_factor"],
                reverse=True,
            )
            for (row, col), m in items:
                lines.append(
                    f"  {str(row):<20} {str(col):<12} {m['trades']:>7} "
                    f"{m['win_rate']:>6.1%} {m['profit_factor']:>8.2f} "
                    f"{m['sharpe']:>8.2f} {m['drawdown']:>7.1%} {m['avg_rr']:>7.2f}"
                )
            lines.append("")

        lines.append(sep)
        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    #  Internal helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _stats(trades: List[TradeRecord]) -> Dict[str, Any]:
        total = len(trades)
        if total == 0:
            return {
                "trades": 0, "wins": 0, "win_rate": 0.0,
                "profit_factor": 0.0, "sharpe": 0.0, "drawdown": 0.0, "avg_rr": 0.0,
            }

        wins = sum(1 for t in trades if t.result == "win")
        losses = sum(1 for t in trades if t.result == "loss")
        win_rate = wins / total if total > 0 else 0.0

        avg_rr = sum(t.rr for t in trades) / total

        # profit factor
        gross_profit = sum(abs(t.profit_loss_pct) for t in trades if t.result == "win")
        gross_loss = sum(abs(t.profit_loss_pct) for t in trades if t.result == "loss")
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)

        # approximate sharpe: WR * PF / std(returns)
        returns = [t.profit_loss_pct for t in trades]
        std = statistics.stdev(returns) if len(returns) > 1 else 1.0
        sharpe = (win_rate * profit_factor) / std if std > 0 else 0.0

        # approximate drawdown: 1 - (win_rate * avg_win / avg_loss)
        avg_win = gross_profit / wins if wins > 0 else 0.0
        avg_loss = gross_loss / losses if losses > 0 else 1.0
        drawdown = 1.0 - (win_rate * avg_win / avg_loss) if avg_loss > 0 else 0.0
        drawdown = max(0.0, min(drawdown, 1.0))

        return {
            "trades": total,
            "wins": wins,
            "win_rate": round(win_rate, 4),
            "profit_factor": round(profit_factor, 4),
            "sharpe": round(sharpe, 4),
            "drawdown": round(drawdown, 4),
            "avg_rr": round(avg_rr, 4),
        }

    def _build_matrix(self, key_fn) -> Dict[Tuple[str, str], Dict[str, Any]]:
        groups: Dict[Tuple[str, str], List[TradeRecord]] = defaultdict(list)
        for t in self._trades:
            rk, ck = key_fn(t)
            if rk is None:
                rk = ""
            if ck is None:
                ck = ""
            groups[(str(rk), str(ck))].append(t)

        return {k: self._stats(v) for k, v in groups.items()}

    def _flatten_all(self, min_trades: int) -> List[Tuple[Tuple[str, str, str], Dict[str, Any]]]:
        """Merge every matrix into (matrix_label, row, col, stats) tuples."""
        flat: List[Tuple[Tuple[str, str, str], Dict[str, Any]]] = []
        for label, matrix in [
            ("Asset x TF", self.asset_by_timeframe()),
            ("Setup x TF", self.setup_by_timeframe()),
            ("Setup x Asset", self.setup_by_asset()),
            ("Regime x Asset", self.regime_by_asset()),
            ("Regime x TF", self.regime_by_timeframe()),
        ]:
            for (row, col), stats in matrix.items():
                if stats["trades"] >= min_trades:
                    flat.append(((label, row, col), stats))
        return flat
