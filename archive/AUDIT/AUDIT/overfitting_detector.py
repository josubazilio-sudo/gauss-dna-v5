import logging
from typing import Any, Dict, List, Optional, Tuple

from .backtest_audit import BacktestResult, TradeRecord
from .monte_carlo import MonteCarloResult

log = logging.getLogger(__name__)


class OverfittingDetector:
    def __init__(
        self,
        backtest_result: BacktestResult,
        monte_carlo_result: Optional[MonteCarloResult] = None,
    ):
        self._result = backtest_result
        self._mc = monte_carlo_result

    def check_walk_forward(self) -> Dict[str, Any]:
        wf = self._result.walk_forward_results
        if not wf or "in_sample" not in wf or "out_sample" not in wf:
            return {
                "check_name": "walk_forward",
                "passed": True,
                "metric": None,
                "threshold": 0.85,
                "detail": "No walk-forward data available",
            }

        is_pf = wf["in_sample"].get("profit_factor", 0) or 0
        oos_pf = wf["out_sample"].get("profit_factor", 0) or 0
        ratio = oos_pf / is_pf if is_pf > 0 else 0
        passed = ratio >= 0.85
        return {
            "check_name": "walk_forward",
            "passed": passed,
            "metric": round(ratio, 4),
            "threshold": 0.85,
            "detail": (
                f"IS PF={is_pf:.2f}, OOS PF={oos_pf:.2f}, "
                f"ratio={ratio:.2%}. "
                f"{'PASS' if passed else 'FAIL'} degradation={' > ' if not passed else ' <= '}15%"
            ),
        }

    def check_monte_carlo(self) -> Dict[str, Any]:
        if self._mc is None:
            return {
                "check_name": "monte_carlo",
                "passed": True,
                "metric": None,
                "threshold": 0.20,
                "detail": "No Monte Carlo result available",
            }

        prob = self._mc.probability_positive
        passed = prob >= 0.20
        return {
            "check_name": "monte_carlo",
            "passed": passed,
            "metric": round(prob, 4),
            "threshold": 0.20,
            "detail": (
                f"P(positive)={prob:.2%}. "
                f"{'PASS' if passed else 'FAIL'} "
                f"threshold=20%"
            ),
        }

    def check_out_of_sample(self) -> Dict[str, Any]:
        trades = self._result.trades
        if len(trades) < 10:
            return {
                "check_name": "out_of_sample",
                "passed": True,
                "metric": None,
                "threshold": 0.85,
                "detail": "Too few trades for out-of-sample split",
            }

        mid = len(trades) // 2
        first = trades[:mid]
        second = trades[mid:]

        def _stats(ts: List[TradeRecord]) -> Tuple[float, float]:
            if not ts:
                return 0, 0
            wins = sum(1 for t in ts if t.result == "win")
            wr = wins / len(ts)
            gross_p = sum(abs(t.profit_loss_pct) for t in ts if t.result == "win")
            gross_l = sum(abs(t.profit_loss_pct) for t in ts if t.result == "loss")
            pf = gross_p / gross_l if gross_l > 0 else 999.0
            return wr, pf

        wr1, pf1 = _stats(first)
        wr2, pf2 = _stats(second)

        pf_ratio = pf2 / pf1 if pf1 > 0 else 0
        wr_ratio = wr2 / wr1 if wr1 > 0 else 0

        passed = pf_ratio >= 0.85
        return {
            "check_name": "out_of_sample",
            "passed": passed,
            "metric": round(pf_ratio, 4),
            "threshold": 0.85,
            "detail": (
                f"First half: WR={wr1:.2%}, PF={pf1:.2f}. "
                f"Second half: WR={wr2:.2%}, PF={pf2:.2f}. "
                f"PF ratio={pf_ratio:.2%}, WR ratio={wr_ratio:.2%}. "
                f"{'PASS' if passed else 'FAIL'} PF degradation > 15%"
            ),
        }

    def check_trade_consistency(self) -> Dict[str, Any]:
        trades = self._result.trades
        if len(trades) < 20:
            return {
                "check_name": "trade_consistency",
                "passed": True,
                "metric": None,
                "threshold": 0.20,
                "detail": "Too few trades for consistency check",
            }

        early = trades[: len(trades) // 2]
        late = trades[len(trades) // 2 :]

        def _wr(ts: List[TradeRecord]) -> float:
            if not ts:
                return 0
            return sum(1 for t in ts if t.result == "win") / len(ts)

        early_wr = _wr(early)
        late_wr = _wr(late)

        diff = abs(early_wr - late_wr)
        passed = diff <= 0.20
        return {
            "check_name": "trade_consistency",
            "passed": passed,
            "metric": round(diff, 4),
            "threshold": 0.20,
            "detail": (
                f"Early WR={early_wr:.2%}, Late WR={late_wr:.2%}, "
                f"diff={diff:.2%}. "
                f"{'PASS' if passed else 'FAIL'} "
                f"WR divergence {'<=' if passed else '>'} 20%"
            ),
        }

    def overall_assessment(self) -> Dict[str, Any]:
        checks = [
            self.check_walk_forward(),
            self.check_monte_carlo(),
            self.check_out_of_sample(),
            self.check_trade_consistency(),
        ]

        warnings: List[str] = []
        failed = 0
        total = 0
        for c in checks:
            if c["metric"] is not None:
                total += 1
                if not c["passed"]:
                    failed += 1
                    warnings.append(
                        f"{c['check_name']}: {c['detail']}"
                    )

        fail_rate = failed / total if total > 0 else 0

        if fail_rate >= 0.5 and failed >= 2:
            verdict = "OVERFITTING LIKELY"
        elif fail_rate > 0 and failed >= 1:
            verdict = "MODERATE RISK"
        else:
            verdict = "ROBUST"

        return {
            "checks": checks,
            "verdict": verdict,
            "warnings": warnings,
            "failed_checks": failed,
            "total_checks": total,
        }

    def summary(self) -> str:
        assessment = self.overall_assessment()
        lines: List[str] = []
        lines.append("=" * 60)
        lines.append("OVERFITTING DETECTOR REPORT")
        lines.append("=" * 60)
        lines.append(f"Verdict: {assessment['verdict']}")
        lines.append(f"Failed checks: {assessment['failed_checks']}/{assessment['total_checks']}")
        lines.append("")
        for c in assessment["checks"]:
            status = "PASS" if c["passed"] else "FAIL"
            lines.append(f"  [{status}] {c['check_name']}")
            if c["metric"] is not None:
                lines.append(f"         metric={c['metric']}  threshold={c['threshold']}")
            lines.append(f"         {c['detail']}")
            lines.append("")
        if assessment["warnings"]:
            lines.append("Warnings:")
            for w in assessment["warnings"]:
                lines.append(f"  - {w}")
        lines.append("=" * 60)
        return "\n".join(lines)
