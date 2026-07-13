import logging
from typing import Dict, List, Optional

from .backtest_types import (
    BacktestResult, Trade, TradeStatus, WalkForwardResult,
    MonteCarloResult, RobustnessResult, AIRecommendation,
)

log = logging.getLogger(__name__)


def generate_report(
    result: BacktestResult,
    wf_result: Optional[WalkForwardResult] = None,
    mc_result: Optional[MonteCarloResult] = None,
    rob_result: Optional[RobustnessResult] = None,
    recommendations: Optional[List[AIRecommendation]] = None,
) -> str:
    lines = []
    lines.append("=" * 70)
    lines.append("BACKTEST INTELLIGENCE REPORT")
    lines.append(f"Total trades: {result.total_trades}")
    lines.append("=" * 70)

    lines.append("\n📊 PERFORMANCE:")
    _add_line(lines, "Win Rate", f"{result.win_rate:.1%}", result.win_rate >= 0.50)
    _add_line(lines, "Profit Factor", f"{result.profit_factor:.2f}", result.profit_factor >= 2.5)
    _add_line(lines, "Expectancy", f"{result.expectancy:.4f}", result.expectancy > 0)
    _add_line(lines, "Net Profit", f"{result.net_profit:.2f}", result.net_profit > 0)
    _add_line(lines, "Gross Profit", f"{result.gross_profit:.2f}")
    _add_line(lines, "Gross Loss", f"{result.gross_loss:.2f}")

    lines.append("\n📉 RISK METRICS:")
    _add_line(lines, "Max Drawdown", f"{result.max_drawdown_pct:.2%}", result.max_drawdown_pct <= 0.10)
    _add_line(lines, "Avg Drawdown", f"{result.avg_drawdown:.4%}")
    _add_line(lines, "Ulcer Index", f"{result.ulcer_index:.4f}")
    _add_line(lines, "Recovery Factor", f"{result.recovery_factor:.2f}")
    _add_line(lines, "Sharpe Ratio", f"{result.sharpe_ratio:.2f}", result.sharpe_ratio >= 1.0)
    _add_line(lines, "Sortino Ratio", f"{result.sortino_ratio:.2f}")
    _add_line(lines, "Calmar Ratio", f"{result.calmar_ratio:.2f}")
    _add_line(lines, "Kelly %", f"{result.kelly_percentage:.1%}")

    lines.append("\n💹 TRADE STATS:")
    _add_line(lines, "Winners", str(result.winning_trades))
    _add_line(lines, "Losers", str(result.losing_trades))
    _add_line(lines, "Avg R", str(result.avg_r))
    _add_line(lines, "Total R", str(result.total_r))
    _add_line(lines, "Avg Holding", f"{result.avg_holding_bars:.0f} bars")
    _add_line(lines, "Final Capital", f"{result.final_capital:.2f}")

    lines.append("\n💰 COSTS:")
    lines.append(f"  Commission: {result.total_commission:.4f}")
    lines.append(f"  Funding:    {result.total_funding:.4f}")
    lines.append(f"  Slippage:   {result.total_slippage:.4f}")

    if wf_result and wf_result.wfa_score > 0:
        lines.append("\n🔬 WALK FORWARD:")
        lines.append(f"  In-Sample Score:     {wf_result.in_sample_score:.4f}")
        lines.append(f"  Out-of-Sample Score: {wf_result.out_sample_score:.4f}")
        lines.append(f"  WFA Score:           {wf_result.wfa_score:.4f}")
        lines.append(f"  Parameter Stability: {wf_result.parameter_stability:.4f}")

    if mc_result and mc_result.simulations > 0:
        lines.append("\n🎲 MONTE CARLO:")
        lines.append(f"  Mean Return:     {mc_result.mean_return:.4f}")
        lines.append(f"  Median Return:   {mc_result.median_return:.4f}")
        lines.append(f"  Std Return:      {mc_result.std_return:.4f}")
        lines.append(f"  VaR 95%:         {mc_result.var_95:.4f}")
        lines.append(f"  VaR 99%:         {mc_result.var_99:.4f}")
        lines.append(f"  P(Positive):     {mc_result.probability_positive:.1%}")
        lines.append(f"  P(PF>1):         {mc_result.probability_profit_factor_gt_1:.1%}")
        lines.append(f"  P(MaxDD<10%):    {mc_result.probability_max_dd_lt_10:.1%}")
        lines.append(f"  Confidence:      {mc_result.confidence_score:.2f}")

    if rob_result and rob_result.robustness_score > 0:
        lines.append("\n🏋️ ROBUSTNESS:")
        lines.append(f"  Robustness Score: {rob_result.robustness_score:.4f}")
        lines.append(f"  Overfitting:      {rob_result.overfitting_score:.4f}")
        lines.append(f"  Underfitting:     {rob_result.underfitting_score:.4f}")
        lines.append(f"  Edge Decay Rate:  {rob_result.edge_decay_rate:.4f}")

    if result.profit_by_setup:
        lines.append("\n📋 PROFIT BY SETUP:")
        for setup, pnl in sorted(result.profit_by_setup.items(), key=lambda x: x[1], reverse=True)[:5]:
            lines.append(f"  {setup:20s}: {pnl:+.2f}")

    if result.profit_by_hour:
        lines.append("\n⏰ PROFIT BY HOUR:")
        for hour in sorted(result.profit_by_hour.keys()):
            lines.append(f"  Hour {hour:>2s}: {result.profit_by_hour[hour]:+.2f}")

    if recommendations:
        critical = [r for r in recommendations if r.priority == "critical"]
        high = [r for r in recommendations if r.priority == "high"]
        if critical:
            lines.append("\n🔴 CRITICAL RECOMMENDATIONS:")
            for r in critical:
                lines.append(f"  ! {r.description}")
                lines.append(f"    Evidence: {r.evidence}")
        if high:
            lines.append("\n🟡 HIGH PRIORITY:")
            for r in high:
                lines.append(f"  - {r.description}")

    lines.append("\n" + "=" * 70)
    return "\n".join(lines)


def _add_line(lines: List[str], label: str, value: str, passed: Optional[bool] = None) -> None:
    icon = ""
    if passed is not None:
        icon = " ✅" if passed else " ❌"
    lines.append(f"  {label:20s}: {value}{icon}")
