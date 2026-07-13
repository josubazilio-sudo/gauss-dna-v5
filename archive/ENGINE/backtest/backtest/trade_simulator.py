import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

from .backtest_types import (
    Trade, TradeDirection, TradeStatus, ExitReason,
    BacktestConfig, BacktestResult,
)
from .backtest_config import ATR_STOP_MULTIPLIER, ATR_TP1_MULTIPLIER, ATR_TP2_MULTIPLIER

log = logging.getLogger(__name__)


def simulate_trade(
    pair: str,
    direction: TradeDirection,
    entry_time: datetime,
    entry_price: float,
    atr: float,
    setup: str,
    regime: str,
    config: BacktestConfig,
    pyramiding_index: int = 0,
    stop_loss_override: Optional[float] = None,
    tp1_override: Optional[float] = None,
    tp2_override: Optional[float] = None,
) -> Trade:
    capital_per_trade = config.initial_capital * config.position_size_pct
    quantity = capital_per_trade / entry_price if entry_price > 0 else 0

    sl = stop_loss_override or _calc_stop(entry_price, direction, atr, config)
    tp1 = tp1_override or _calc_tp1(entry_price, direction, atr, config)
    tp2 = tp2_override or _calc_tp2(entry_price, direction, atr, config)

    commission = entry_price * quantity * config.commission_pct
    slippage = entry_price * quantity * config.slippage_pct

    return Trade(
        id=uuid4().hex[:12],
        pair=pair,
        direction=direction,
        entry_time=entry_time,
        exit_time=None,
        entry_price=entry_price,
        exit_price=None,
        stop_loss=sl,
        take_profit_1=tp1,
        take_profit_2=tp2,
        quantity=quantity,
        commission_paid=commission,
        funding_paid=0.0,
        slippage_paid=slippage,
        status=TradeStatus.OPEN,
        pnl=0.0,
        pnl_percent=0.0,
        holding_bars=0,
        atr_at_entry=atr,
        setup=setup,
        regime=regime,
        r_multiple=0.0,
        exit_reason=None,
        pyramiding_index=pyramiding_index,
    )


def close_trade(trade: Trade, exit_price: float, exit_time: datetime,
                 exit_reason: ExitReason, config: BacktestConfig) -> Trade:
    if trade.direction == TradeDirection.LONG:
        raw_pnl = (exit_price - trade.entry_price) * trade.quantity
        exit_commission = exit_price * trade.quantity * config.commission_pct
    else:
        raw_pnl = (trade.entry_price - exit_price) * trade.quantity
        exit_commission = exit_price * trade.quantity * config.commission_pct

    total_commission = trade.commission_paid + exit_commission
    total_slippage = trade.slippage_paid + exit_price * trade.quantity * config.slippage_pct
    net_pnl = raw_pnl - total_commission - total_slippage - trade.funding_paid

    pnl_pct = net_pnl / (trade.entry_price * trade.quantity) if trade.entry_price * trade.quantity > 0 else 0.0
    r_multiple = (exit_price - trade.entry_price) / (trade.entry_price - trade.stop_loss) if (
        trade.entry_price - trade.stop_loss) != 0 else 0.0
    if trade.direction == TradeDirection.SHORT:
        r_multiple = (trade.entry_price - exit_price) / (trade.stop_loss - trade.entry_price) if (
            trade.stop_loss - trade.entry_price) != 0 else 0.0

    status = TradeStatus.WIN if net_pnl > 0 else (TradeStatus.LOSS if net_pnl < 0 else TradeStatus.BREAK_EVEN)
    holding = (exit_time - trade.entry_time).total_seconds() / 60 if exit_time > trade.entry_time else 0

    trade.exit_time = exit_time
    trade.exit_price = exit_price
    trade.status = status
    trade.pnl = round(net_pnl, 4)
    trade.pnl_percent = round(pnl_pct, 6)
    trade.holding_bars = int(holding)
    trade.r_multiple = round(r_multiple, 4)
    trade.exit_reason = exit_reason
    trade.commission_paid = round(total_commission, 4)
    trade.slippage_paid = round(total_slippage, 4)
    return trade


def _calc_stop(price: float, direction: TradeDirection, atr: float, config: BacktestConfig) -> float:
    if not config.use_atr_stop:
        return price * (0.98 if direction == TradeDirection.LONG else 1.02)
    mult = config.atr_stop_multiplier or ATR_STOP_MULTIPLIER
    if direction == TradeDirection.LONG:
        return price - atr * mult
    return price + atr * mult


def _calc_tp1(price: float, direction: TradeDirection, atr: float, config: BacktestConfig) -> float:
    mult = config.atr_tp1_multiplier or ATR_TP1_MULTIPLIER
    if direction == TradeDirection.LONG:
        return price + atr * mult
    return price - atr * mult


def _calc_tp2(price: float, direction: TradeDirection, atr: float, config: BacktestConfig) -> float:
    mult = config.atr_tp2_multiplier or ATR_TP2_MULTIPLIER
    if direction == TradeDirection.LONG:
        return price + atr * mult
    return price - atr * mult
