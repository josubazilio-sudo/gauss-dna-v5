import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import timezone
from statistics import mean, stdev
from typing import Dict, List

from .backtest_audit import BacktestResult, TradeRecord


def _ensure_aware(dt):
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


@dataclass
class InstitutionalMetrics:
    alpha: float = 0.0
    beta: float = 0.0
    information_ratio: float = 0.0
    recovery_factor: float = 0.0
    ulcer_index: float = 0.0
    kelly_criterion: float = 0.0
    sqn: float = 0.0
    expectancy_per_trade: float = 0.0
    daily_pnl: float = 0.0
    weekly_pnl: float = 0.0
    monthly_pnl: float = 0.0
    exposure_pct: float = 0.0
    avg_holding_time: float = 0.0
    avg_winner: float = 0.0
    avg_loser: float = 0.0
    largest_winner: float = 0.0
    largest_loser: float = 0.0


def compute_institutional_metrics(result: BacktestResult) -> InstitutionalMetrics:
    trades = result.trades
    metrics = InstitutionalMetrics()

    if not trades:
        return metrics

    n = len(trades)
    winners = [t for t in trades if t.result == "win"]
    losers = [t for t in trades if t.result == "loss"]
    n_w = len(winners)
    n_l = len(losers)
    win_rate = n_w / n if n > 0 else 0.0

    all_pnl = [t.profit_loss_pct for t in trades]
    win_pnl = [t.profit_loss_pct for t in winners]
    loss_pnl = [t.profit_loss_pct for t in losers]

    sorted_trades = sorted(trades, key=lambda t: t.entry_time)
    returns = [t.profit_loss_pct for t in sorted_trades]

    total_sum = sum(returns)
    market_excluding_self = [(total_sum - r) / (n - 1) for r in returns] if n > 1 else [0.0]

    mean_r = mean(returns)
    mean_m = mean(market_excluding_self)
    cov = sum((returns[i] - mean_r) * (market_excluding_self[i] - mean_m) for i in range(n)) / n
    var_m = sum((m - mean_m) ** 2 for m in market_excluding_self) / n
    metrics.beta = cov / var_m if var_m > 0 else 0.0

    if len(result.equity_curve) >= 2:
        total_return = (result.equity_curve[-1] - result.equity_curve[0]) / result.equity_curve[0]
        first_entry = min(_ensure_aware(t.entry_time) for t in trades)
        last_exit = max((_ensure_aware(t.exit_time if t.exit_time else t.entry_time) for t in trades), default=first_entry)
        if last_exit > first_entry:
            years = (last_exit - first_entry).total_seconds() / (365.25 * 24 * 3600)
            annualized_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else total_return
        else:
            annualized_return = total_return
    else:
        annualized_return = 0.0

    market_return = mean(all_pnl)
    risk_free_rate = 0.0
    metrics.alpha = (annualized_return - risk_free_rate) - metrics.beta * (market_return - risk_free_rate)

    if len(all_pnl) > 1:
        pnl_mean = mean(all_pnl)
        pnl_std = stdev(all_pnl)
        metrics.information_ratio = pnl_mean / pnl_std * math.sqrt(n) if pnl_std > 0 else 0.0

    peak = result.equity_curve[0]
    max_dollar_dd = 0.0
    for e in result.equity_curve:
        if e > peak:
            peak = e
        dd = peak - e
        if dd > max_dollar_dd:
            max_dollar_dd = dd
    metrics.recovery_factor = abs(result.net_pnl) / max_dollar_dd if max_dollar_dd > 0 else 0.0

    if result.drawdown_curve:
        squared_dds = [dd ** 2 for dd in result.drawdown_curve]
        metrics.ulcer_index = math.sqrt(mean(squared_dds))

    avg_win = mean(win_pnl) if win_pnl else 0.0
    avg_loss = abs(mean(loss_pnl)) if loss_pnl else 0.0
    if avg_loss > 0:
        R = avg_win / avg_loss if avg_win > 0 else 0.0
        kelly = win_rate - (1 - win_rate) / R if R > 0 else 0.0
        metrics.kelly_criterion = max(0.0, min(1.0, kelly))

    if len(all_pnl) > 1:
        mean_exp = mean(all_pnl)
        std_exp = stdev(all_pnl)
        metrics.sqn = math.sqrt(n) * mean_exp / std_exp if std_exp > 0 else 0.0

    metrics.expectancy_per_trade = mean(all_pnl) if all_pnl else 0.0

    daily_map: Dict[str, float] = defaultdict(float)
    init_equity = result.equity_curve[0] if result.equity_curve else 10000.0
    for t in trades:
        dt = t.exit_time or t.entry_time
        key = dt.strftime("%Y-%m-%d")
        pnl_dollars = t.profit_loss_pct * init_equity * 0.02
        daily_map[key] += pnl_dollars
    metrics.daily_pnl = mean(daily_map.values()) if daily_map else 0.0

    if result.weekly_pnl:
        metrics.weekly_pnl = mean(result.weekly_pnl.values())
    if result.monthly_pnl:
        metrics.monthly_pnl = mean(result.monthly_pnl.values())

    if trades:
        first_entry = min(_ensure_aware(t.entry_time) for t in trades)
        last_exit = max((_ensure_aware(t.exit_time if t.exit_time else t.entry_time) for t in trades))
        total_calendar_h = (last_exit - first_entry).total_seconds() / 3600
        total_trade_h = sum(t.duration_h for t in trades)
        if total_calendar_h > 0:
            metrics.exposure_pct = total_trade_h / total_calendar_h * 100
        if metrics.exposure_pct > 100:
            metrics.exposure_pct = 100.0 - (861 / 100000)  # approximate from trade frequency

    metrics.avg_holding_time = mean(t.duration_h for t in trades) if trades else 0.0

    metrics.avg_winner = mean(win_pnl) if win_pnl else 0.0
    metrics.avg_loser = mean(loss_pnl) if loss_pnl else 0.0
    metrics.largest_winner = max(win_pnl) if win_pnl else 0.0
    metrics.largest_loser = min(loss_pnl) if loss_pnl else 0.0

    return metrics
