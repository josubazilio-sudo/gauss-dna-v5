import logging
import math
from typing import Dict, List, Tuple

from .backtest_types import Trade, TradeStatus, TradeDirection, BacktestResult
from .backtest_config import RISK_FREE_RATE, TRADING_DAYS_PER_YEAR

log = logging.getLogger(__name__)


def compute_statistics(trades: List[Trade], equity_curve: List[float],
                       initial_capital: float, final_capital: float) -> BacktestResult:
    result = BacktestResult()

    if not trades:
        return result

    result.total_trades = len(trades)
    result.winning_trades = sum(1 for t in trades if t.status == TradeStatus.WIN)
    result.losing_trades = sum(1 for t in trades if t.status == TradeStatus.LOSS)
    result.break_even_trades = sum(1 for t in trades if t.status == TradeStatus.BREAK_EVEN)

    result.win_rate = result.winning_trades / result.total_trades if result.total_trades > 0 else 0.0

    winners = [t for t in trades if t.status == TradeStatus.WIN]
    losers = [t for t in trades if t.status == TradeStatus.LOSS]

    gross_profit = sum(t.pnl for t in winners)
    gross_loss = abs(sum(t.pnl for t in losers))
    result.gross_profit = round(gross_profit, 4)
    result.gross_loss = round(gross_loss, 4)
    result.net_profit = round(sum(t.pnl for t in trades), 4)
    result.final_capital = final_capital

    result.profit_factor = gross_profit / gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)

    avg_win = gross_profit / len(winners) if winners else 0.0
    avg_loss = gross_loss / len(losers) if losers else 0.0
    wr = result.win_rate
    result.expectancy = wr * avg_win - (1 - wr) * avg_loss if result.total_trades > 0 else 0.0

    result.total_commission = round(sum(t.commission_paid for t in trades), 4)
    result.total_funding = round(sum(t.funding_paid for t in trades), 4)
    result.total_slippage = round(sum(t.slippage_paid for t in trades), 4)

    result.avg_r = round(sum(t.r_multiple for t in trades) / len(trades), 4) if trades else 0.0
    result.total_r = round(sum(t.r_multiple for t in trades), 4)

    result.avg_holding_bars = round(sum(t.holding_bars for t in trades) / len(trades), 2) if trades else 0.0

    if equity_curve and len(equity_curve) > 1:
        result.equity_curve = equity_curve
        result.max_drawdown, result.max_drawdown_pct, result.avg_drawdown, dd_curve = _compute_drawdown(equity_curve)
        result.drawdown_curve = dd_curve
        result.recovery_factor = result.net_profit / result.max_drawdown if result.max_drawdown > 0 else 0.0
        result.ulcer_index = _compute_ulcer(dd_curve)

        returns = _compute_returns(equity_curve)
        result.sharpe_ratio = _compute_sharpe(returns)
        result.sortino_ratio = _compute_sortino(returns)

        if result.max_drawdown_pct > 0:
            total_return = (final_capital - initial_capital) / initial_capital if initial_capital > 0 else 0
            cagr = total_return
            result.calmar_ratio = cagr / result.max_drawdown_pct if result.max_drawdown_pct > 0 else 0.0

    if avg_win > 0 and avg_loss > 0:
        result.kelly_percentage = wr - (1 - wr) / (avg_win / avg_loss) if avg_loss > 0 else 0.0
        result.kelly_percentage = max(0.0, min(result.kelly_percentage, 1.0))

    result.profit_by_setup = _group_by(trades, "setup")
    result.profit_by_regime = _group_by(trades, "regime")
    result.profit_by_hour = _group_by_hour(trades)
    result.profit_by_day = _group_by_day(trades)
    result.profit_by_pair = _group_by(trades, "pair")
    result.profit_by_timeframe = _group_by(trades, "setup")

    return result


def _compute_drawdown(equity: List[float]) -> Tuple[float, float, float, List[float]]:
    if not equity:
        return 0.0, 0.0, 0.0, []
    peak = equity[0]
    max_dd = 0.0
    max_dd_pct = 0.0
    total_dd = 0.0
    dd_count = 0
    dd_curve = [0.0]
    for val in equity:
        if val > peak:
            peak = val
        dd = peak - val
        dd_pct = dd / peak if peak > 0 else 0
        dd_curve.append(dd_pct)
        if dd > max_dd:
            max_dd = dd
            max_dd_pct = dd_pct
        total_dd += dd_pct
        dd_count += 1
    avg_dd = total_dd / dd_count if dd_count > 0 else 0.0
    return round(max_dd, 4), round(max_dd_pct, 6), round(avg_dd, 6), dd_curve


def _compute_ulcer(dd_curve: List[float]) -> float:
    if not dd_curve:
        return 0.0
    squared = sum(d * d for d in dd_curve)
    return round(math.sqrt(squared / len(dd_curve)), 6)


def _compute_returns(equity: List[float]) -> List[float]:
    if len(equity) < 2:
        return []
    return [(equity[i] - equity[i - 1]) / equity[i - 1] if equity[i - 1] > 0 else 0.0
            for i in range(1, len(equity))]


def _compute_sharpe(returns: List[float]) -> float:
    if len(returns) < 2:
        return 0.0
    avg_ret = sum(returns) / len(returns)
    var = sum((r - avg_ret) ** 2 for r in returns) / (len(returns) - 1)
    std = math.sqrt(var) if var > 0 else 0.0001
    excess = avg_ret - RISK_FREE_RATE / TRADING_DAYS_PER_YEAR
    sharpe = (excess / std) * math.sqrt(TRADING_DAYS_PER_YEAR)
    return round(sharpe, 4)


def _compute_sortino(returns: List[float]) -> float:
    if len(returns) < 2:
        return 0.0
    avg_ret = sum(returns) / len(returns)
    downside = [r for r in returns if r < 0]
    if not downside:
        return 10.0
    d_var = sum((r - avg_ret) ** 2 for r in downside) / len(downside)
    d_std = math.sqrt(d_var) if d_var > 0 else 0.0001
    excess = avg_ret - RISK_FREE_RATE / TRADING_DAYS_PER_YEAR
    sortino = (excess / d_std) * math.sqrt(TRADING_DAYS_PER_YEAR)
    return round(sortino, 4)


def _group_by(trades: List[Trade], attr: str) -> Dict[str, float]:
    result: Dict[str, float] = {}
    for t in trades:
        key = getattr(t, attr, "unknown")
        result[key] = round(result.get(key, 0.0) + t.pnl, 4)
    return result


def _group_by_hour(trades: List[Trade]) -> Dict[str, float]:
    result: Dict[str, float] = {}
    for t in trades:
        if t.exit_time:
            hour = str(t.exit_time.hour)
            result[hour] = round(result.get(hour, 0.0) + t.pnl, 4)
    return result


def _group_by_day(trades: List[Trade]) -> Dict[str, float]:
    result: Dict[str, float] = {}
    for t in trades:
        if t.exit_time:
            day = t.exit_time.strftime("%A")
            result[day] = round(result.get(day, 0.0) + t.pnl, 4)
    return result
