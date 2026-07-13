import json
import logging
import os
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean
from typing import Dict, List, Optional, Any

log = logging.getLogger(__name__)


class PaperTrade:
    def __init__(self, pair: str, direction: str, entry_price: float,
                 stop_loss: float, take_profit: float,
                 entry_time: str, cycle: int, quality: float, setup: str, regime: str,
                 signal_id: str = "", position_value: float = 0.0,
                 take_profit_2: float = 0.0,
                 partial_tp: float = 0.0,
                 break_even_price: float = 0.0):
        self.id = str(uuid.uuid4())[:8]
        self.pair = pair
        self.direction = direction
        self.entry_price = entry_price
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.take_profit_2 = take_profit_2
        self.partial_tp = partial_tp
        self.break_even_price = break_even_price if break_even_price > 0 else entry_price
        self.entry_time = entry_time
        self.exit_price: Optional[float] = None
        self.exit_time: Optional[str] = None
        self.exit_reason: str = ""
        self.signal_id = signal_id
        self.cycle = cycle
        self.quality = quality
        self.setup = setup
        self.regime = regime
        self.position_value = position_value
        self.pnl: float = 0.0
        self.pnl_percent: float = 0.0
        self.r_multiple: float = 0.0
        self.status: str = "OPEN"
        self.partial_filled: bool = False
        self.trailing_active: bool = False
        self.trailing_stop_level: Optional[float] = None
        self.remaining_value: float = position_value
        self.highest_seen: float = entry_price
        self.lowest_seen: float = entry_price
        self.max_profit_before_reversal: float = 0.0

    def close(self, exit_price: float, exit_time: str, atr: float = 0.0):
        if not exit_price or exit_price <= 0:
            log.error(f"PaperTrade: invalid exit_price {exit_price} for {self.pair}")
            return

        self.exit_price = exit_price
        self.exit_time = exit_time

        if self.direction == "LONG":
            self.pnl = exit_price - self.entry_price
            self.pnl_percent = (exit_price - self.entry_price) / self.entry_price * 100
        else:
            self.pnl = self.entry_price - exit_price
            self.pnl_percent = (self.entry_price - exit_price) / self.entry_price * 100

        if atr > 0 and self.entry_price > 0:
            self.r_multiple = self.pnl / (atr * self.entry_price)

        self.status = "WIN" if self.pnl > 0 else ("LOSS" if self.pnl < 0 else "BREAK_EVEN")


class PaperTradingEngine:
    """Registra sinais aprovados como operacoes de papel e monitora saidas."""

    def __init__(self, db_path: str = "MEMORY/paper_trading.json"):
        self._db_path = db_path
        self._open_trades: Dict[str, PaperTrade] = {}
        self._closed_trades: List[PaperTrade] = []
        self._capital: float = 10000.0
        self._max_concurrent: int = 5
        self._initial_capital: float = 10000.0
        self._load()

    def _load(self):
        if os.path.exists(self._db_path):
            try:
                with open(self._db_path) as f:
                    data = json.load(f)
                    self._capital = data.get("capital", 10000.0)
                    self._initial_capital = data.get("initial_capital", 10000.0)
                    trades = data.get("closed_trades", [])
                    for t in trades:
                        pt = PaperTrade(
                            t["pair"], t["direction"], t["entry_price"],
                            t.get("stop_loss", 0), t.get("take_profit", 0),
                            t["entry_time"], t["cycle"], t.get("quality", 0),
                            t.get("setup", ""), t.get("regime", ""),
                            signal_id=t.get("signal_id", ""),
                            position_value=t.get("position_value", 0),
                            take_profit_2=t.get("take_profit_2", 0),
                            partial_tp=t.get("partial_tp", 0),
                            break_even_price=t.get("break_even_price", 0),
                        )
                        pt.exit_price = t.get("exit_price")
                        pt.exit_time = t.get("exit_time")
                        pt.exit_reason = t.get("exit_reason", "")
                        pt.status = t.get("status", "CLOSED")
                        pt.pnl = t.get("pnl", 0.0)
                        pt.pnl_percent = t.get("pnl_percent", 0.0)
                        pt.r_multiple = t.get("r_multiple", 0.0)
                        pt.partial_filled = t.get("partial_filled", False)
                        pt.trailing_active = t.get("trailing_active", False)
                        pt.trailing_stop_level = t.get("trailing_stop_level")
                        pt.remaining_value = t.get("remaining_value", pt.position_value)
                        pt.highest_seen = t.get("highest_seen", pt.entry_price)
                        pt.lowest_seen = t.get("lowest_seen", pt.entry_price)
                        pt.max_profit_before_reversal = t.get("max_profit_before_reversal", 0.0)
                        self._closed_trades.append(pt)
                log.info(f"PaperTrading: loaded {len(self._closed_trades)} closed trades, capital={self._capital:.2f}")
            except Exception as e:
                log.warning(f"PaperTrading: load error {e}")

    def _save(self):
        data = {
            "capital": self._capital,
            "initial_capital": self._initial_capital,
            "total_trades": len(self._closed_trades),
            "open_trades": len(self._open_trades),
            "closed_trades": [{
                "id": t.id, "pair": t.pair, "direction": t.direction,
                "entry_price": t.entry_price, "stop_loss": t.stop_loss,
                "take_profit": t.take_profit,
                "take_profit_2": t.take_profit_2,
                "partial_tp": t.partial_tp,
                "break_even_price": t.break_even_price,
                "entry_time": t.entry_time,
                "exit_price": t.exit_price, "exit_time": t.exit_time,
                "status": t.status, "pnl": t.pnl, "pnl_percent": t.pnl_percent,
                "r_multiple": t.r_multiple, "cycle": t.cycle,
                "quality": t.quality, "setup": t.setup, "regime": t.regime,
                "signal_id": t.signal_id, "position_value": t.position_value,
                "exit_reason": t.exit_reason,
                "partial_filled": t.partial_filled,
                "trailing_active": t.trailing_active,
                "trailing_stop_level": t.trailing_stop_level,
                "remaining_value": t.remaining_value,
                "highest_seen": t.highest_seen,
                "lowest_seen": t.lowest_seen,
                "max_profit_before_reversal": t.max_profit_before_reversal,
            } for t in self._closed_trades],
        }
        os.makedirs(os.path.dirname(self._db_path) if os.path.dirname(self._db_path) else ".", exist_ok=True)
        with open(self._db_path, "w") as f:
            json.dump(data, f, indent=2)

    def record_entry(self, pair: str, direction: str, entry_price: float,
                     stop_loss: float, take_profit: float,
                     cycle: int, quality: float = 0, setup: str = "", regime: str = "",
                     signal_id: str = "",
                     take_profit_2: float = 0.0,
                     partial_tp: float = 0.0,
                     break_even_price: float = 0.0):
        if entry_price <= 0 or stop_loss <= 0 or take_profit <= 0:
            log.error(f"PaperTrade: invalid entry/stop/tp ({entry_price}/{stop_loss}/{take_profit}) for {pair}")
            return None

        # Check for existing open trade on same pair+direction (update it)
        existing = None
        for t in self._open_trades.values():
            if t.pair == pair and t.direction == direction and t.status == "OPEN":
                existing = t
                break
        if existing:
            old_entry = existing.entry_price
            old_stop = existing.stop_loss
            existing.entry_price = entry_price
            existing.stop_loss = stop_loss
            existing.take_profit = take_profit
            existing.take_profit_2 = take_profit_2 or existing.take_profit_2
            existing.quality = quality
            existing.signal_id = signal_id or existing.signal_id
            log.info(f"PaperTrade UPDATE: {pair} {direction} entry={old_entry:.4f}->{entry_price:.4f} "
                     f"SL={old_stop:.4f}->{stop_loss:.4f} TP={take_profit:.4f}")
            return existing

        if len(self._open_trades) >= self._max_concurrent:
            log.debug(f"PaperTrading: max concurrent trades ({self._max_concurrent}) reached, skipping {pair}")
            return None

        risk_per_trade = self._capital * 0.02
        stop_pct = abs(entry_price - stop_loss) / entry_price if entry_price > 0 else 0.02
        stop_pct = max(stop_pct, 0.001)
        position_value = risk_per_trade / stop_pct if stop_pct > 0 else 0

        pt = PaperTrade(pair, direction, entry_price, stop_loss, take_profit,
                        datetime.now(timezone.utc).isoformat(),
                        cycle, quality, setup, regime,
                        signal_id=signal_id, position_value=position_value,
                        take_profit_2=take_profit_2,
                        partial_tp=partial_tp,
                        break_even_price=break_even_price)
        self._open_trades[pt.id] = pt
        log.info(f"PaperTrade ENTRY: {pair} {direction} @ {entry_price:.4f} "
                 f"SL={stop_loss:.4f} TP1={take_profit:.4f} TP2={take_profit_2:.4f} "
                 f"partial={partial_tp:.4f} pos={position_value:.2f}USDT (id={pt.id})")
        return pt

    def check_exits(self, current_prices: Dict[str, float], atrs: Dict[str, float] = None,
                    closes: Dict[str, List[float]] = None):
        """Check if open trades should be closed based on current prices.
        Suporta V19.0: take parcial, trailing stop, break-even.
        """
        closed = []
        for tid, trade in list(self._open_trades.items()):
            pair = trade.pair
            current_price = current_prices.get(pair)
            if current_price is None:
                continue
            if current_price <= 0:
                log.warning(f"PaperTrade: invalid current_price {current_price} for {pair}, skipping")
                continue

            atr = (atrs or {}).get(pair, 0.0)
            pair_closes = (closes or {}).get(pair, [])
            is_long = trade.direction == "LONG"

            if current_price > trade.highest_seen:
                trade.highest_seen = current_price
            if current_price < trade.lowest_seen:
                trade.lowest_seen = current_price
            if is_long:
                mfe_pct = (trade.highest_seen - trade.entry_price) / trade.entry_price * 100
                mae_pct = (trade.entry_price - trade.lowest_seen) / trade.entry_price * 100
                curr_profit = (current_price - trade.entry_price) / trade.entry_price * 100
            else:
                mfe_pct = (trade.entry_price - trade.lowest_seen) / trade.entry_price * 100
                mae_pct = (trade.highest_seen - trade.entry_price) / trade.entry_price * 100
                curr_profit = (trade.entry_price - current_price) / trade.entry_price * 100
            if curr_profit > trade.max_profit_before_reversal:
                trade.max_profit_before_reversal = curr_profit

            close = False
            reason = ""
            is_long = trade.direction == "LONG"

            # 1. Check stop loss primeiro (sempre)
            sl_hit = (is_long and current_price <= trade.stop_loss) or (not is_long and current_price >= trade.stop_loss)
            if sl_hit:
                close = True
                reason = "stop_loss"

            # 2. Check trailing stop (se ativo)
            if not close and trade.trailing_active and trade.trailing_stop_level is not None:
                ts_hit = (is_long and current_price <= trade.trailing_stop_level) or (not is_long and current_price >= trade.trailing_stop_level)
                if ts_hit:
                    close = True
                    reason = "trailing_stop"

            # 3. V19.0: Take parcial (50% aos +2% ou 1 ATR)
            if not close and not trade.partial_filled and trade.partial_tp > 0:
                partial_hit = (is_long and current_price >= trade.partial_tp) or (not is_long and current_price <= trade.partial_tp)
                if partial_hit:
                    trade.partial_filled = True
                    partial_pnl = trade.remaining_value * 0.5 * (trade.partial_tp / trade.entry_price - 1) if is_long else trade.remaining_value * 0.5 * (1 - trade.partial_tp / trade.entry_price)
                    trade.remaining_value *= 0.5
                    self._capital += partial_pnl
                    trade.stop_loss = trade.break_even_price
                    log.info(f"PaperTrade PARTIAL: {pair} {trade.direction} "
                             f"@ {current_price:.4f} PnL={partial_pnl:+.2f}USDT | SL movido para BE")
                    # Update stop in self._paper for main loop
                    trade.stop_loss = trade.break_even_price

            # 4. V19.0: TP1 atingido -> ativar trailing (se TP2 existir) ou fechar
            if not close and not trade.trailing_active:
                tp1_hit = (is_long and current_price >= trade.take_profit) or (not is_long and current_price <= trade.take_profit)
                if tp1_hit:
                    if trade.take_profit_2 > 0:
                        trade.trailing_active = True
                        trade.trailing_stop_level = trade.entry_price
                        log.info(f"PaperTrade TP1: {pair} {trade.direction} @ {current_price:.4f} | Trailing ativado")
                    else:
                        close = True
                        reason = "take_profit"

            # 5. V19.0: Atualizar trailing stop
            if not close and trade.trailing_active:
                try:
                    from ENGINE.risk.tp_adaptativo import calculate_trailing_stop
                    new_ts = calculate_trailing_stop(
                        current_price=current_price,
                        entry_price=trade.entry_price,
                        direction=trade.direction,
                        atr=atr,
                        closes=pair_closes if pair_closes else [trade.entry_price] * 30,
                    )
                    if new_ts is not None:
                        if is_long:
                            if trade.trailing_stop_level is None or new_ts > trade.trailing_stop_level:
                                trade.trailing_stop_level = new_ts
                        else:
                            if trade.trailing_stop_level is None or new_ts < trade.trailing_stop_level:
                                trade.trailing_stop_level = new_ts
                except Exception as e:
                    log.debug(f"Trailing stop calc error: {e}")

            # 6. TP2 (caso nao tenha saido ainda)
            if not close and trade.take_profit_2 > 0:
                tp2_hit = (is_long and current_price >= trade.take_profit_2) or (not is_long and current_price <= trade.take_profit_2)
                if tp2_hit:
                    close = True
                    reason = "take_profit_2"

            # 7. TP1 original (caso trailing nao esteja ativo e TP2 nao exista)
            if not close and not trade.trailing_active and trade.take_profit_2 == 0:
                tp1_hit = (is_long and current_price >= trade.take_profit) or (not is_long and current_price <= trade.take_profit)
                if tp1_hit:
                    close = True
                    reason = "take_profit"

            if close:
                value_for_close = trade.remaining_value if trade.partial_filled else trade.position_value
                if value_for_close <= 0:
                    value_for_close = trade.position_value * (trade.remaining_value / trade.position_value) if trade.position_value > 0 else trade.position_value

                trade.exit_reason = reason
                trade.close(current_price, datetime.now(timezone.utc).isoformat(), atr)
                if trade.exit_price is None or trade.exit_price <= 0:
                    log.error(f"PaperTrade: close failed for {pair} (exit={trade.exit_price})")
                    continue
                pnl_usdt = value_for_close * (trade.pnl_percent / 100)
                self._capital += pnl_usdt
                self._closed_trades.append(trade)
                closed.append(trade)
                del self._open_trades[tid]
                log.info(f"PaperTrade EXIT: {pair} {trade.direction} "
                         f"PnL={trade.pnl_percent:+.2f}% ({pnl_usdt:+.2f}USDT) | {reason}")

        self._save()
        return closed

    def get_stats(self) -> Dict:
        """V19.0: estatisticas avancadas de Paper Trading."""
        if not self._closed_trades:
            return {"status": "no_trades", "total_trades": 0}

        wins = [t for t in self._closed_trades if t.status == "WIN"]
        losses = [t for t in self._closed_trades if t.status == "LOSS"]
        total = len(self._closed_trades)

        win_rate = len(wins) / total if total > 0 else 0
        gross_profit = sum(t.pnl for t in wins)
        gross_loss = abs(sum(t.pnl for t in losses))
        pf = gross_profit / gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0)

        net_profit = sum(t.pnl for t in self._closed_trades)

        equity_curve = [self._initial_capital]
        for t in self._closed_trades:
            equity_curve.append(equity_curve[-1] + t.pnl)

        peak = equity_curve[0]
        max_dd = 0.0
        max_dd_pct = 0.0
        for v in equity_curve:
            if v > peak:
                peak = v
            dd = peak - v
            dd_pct = dd / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
                max_dd_pct = dd_pct

        avg_win = gross_profit / len(wins) if wins else 0
        avg_loss = gross_loss / len(losses) if losses else 0
        expectancy = win_rate * avg_win - (1 - win_rate) * avg_loss
        payoff = avg_win / avg_loss if avg_loss > 0 else (avg_win if avg_win > 0 else 0)

        returns = [t.pnl_percent for t in self._closed_trades]
        avg_return = mean(returns) if returns else 0
        std_returns = (sum((r - avg_return) ** 2 for r in returns) / len(returns)) ** 0.5 if len(returns) > 1 else 0
        sharpe = (avg_return - 0.5) / std_returns if std_returns > 0 else 0

        partial_count = sum(1 for t in self._closed_trades if t.partial_filled)
        trailing_wins = sum(1 for t in wins if t.trailing_active)
        be_exits = sum(1 for t in self._closed_trades if t.status == "BREAK_EVEN")
        tp1_trades = [t for t in wins if not t.take_profit_2 or (t.trailing_active and t.exit_reason not in ("take_profit_2",))]
        tp2_trades = [t for t in wins if t.exit_reason == "take_profit_2"]
        avg_tp1_profit = mean([t.pnl_percent for t in tp1_trades]) if tp1_trades else 0
        avg_tp2_profit = mean([t.pnl_percent for t in tp2_trades]) if tp2_trades else 0
        avg_r = sum(t.r_multiple for t in self._closed_trades) / total if total > 0 else 0

        tp_effs = []
        for t in self._closed_trades:
            if t.take_profit > 0 and t.entry_price > 0:
                try:
                    max_reached = t.highest_seen if t.direction == "LONG" else t.lowest_seen
                    if t.direction == "LONG":
                        max_pct = (max_reached - t.entry_price) / t.entry_price * 100
                        tp_pct = (t.take_profit - t.entry_price) / t.entry_price * 100
                    else:
                        max_pct = (t.entry_price - max_reached) / t.entry_price * 100
                        tp_pct = (t.entry_price - t.take_profit) / t.entry_price * 100
                    if tp_pct > 0:
                        eff = min(max_pct / tp_pct * 100, 100.0)
                        tp_effs.append(eff)
                except Exception:
                    pass
        avg_tp_eff = mean(tp_effs) if tp_effs else 0

        # V19.0: win rate por classificacao
        win_by_class = {}
        for t in self._closed_trades:
            cls = getattr(t, 'classification_label', None) or getattr(t, 'setup', 'unknown')
            if cls not in win_by_class:
                win_by_class[cls] = {"wins": 0, "total": 0}
            win_by_class[cls]["total"] += 1
            if t.status == "WIN":
                win_by_class[cls]["wins"] += 1
        win_rate_by_class = {
            cls: round(data["wins"] / data["total"] * 100, 1)
            for cls, data in win_by_class.items()
        }

        # V19.0: win rate por simbolo
        win_by_sym = {}
        for t in self._closed_trades:
            sym = t.pair
            if sym not in win_by_sym:
                win_by_sym[sym] = {"wins": 0, "total": 0}
            win_by_sym[sym]["total"] += 1
            if t.status == "WIN":
                win_by_sym[sym]["wins"] += 1
        win_rate_by_symbol = {
            sym: round(data["wins"] / data["total"] * 100, 1)
            for sym, data in win_by_sym.items()
        }

        # V19.0: win rate por timeframe
        win_by_tf = {}
        for t in self._closed_trades:
            tf = getattr(t, 'timeframe', 'unknown')
            if tf not in win_by_tf:
                win_by_tf[tf] = {"wins": 0, "total": 0}
            win_by_tf[tf]["total"] += 1
            if t.status == "WIN":
                win_by_tf[tf]["wins"] += 1
        win_rate_by_tf = {
            tf: round(data["wins"] / data["total"] * 100, 1)
            for tf, data in win_by_tf.items()
        }

        # V19.0: win rate LONG vs SHORT
        long_trades = [t for t in self._closed_trades if t.direction == "LONG"]
        short_trades = [t for t in self._closed_trades if t.direction == "SHORT"]
        long_wins = sum(1 for t in long_trades if t.status == "WIN")
        short_wins = sum(1 for t in short_trades if t.status == "WIN")

        # V19.0: tempo medio ate TP e Stop
        tp_times = []
        stop_times = []
        for t in self._closed_trades:
            if t.entry_time and t.exit_time:
                try:
                    from datetime import datetime as _dt
                    entry_dt = _dt.fromisoformat(t.entry_time)
                    exit_dt = _dt.fromisoformat(t.exit_time)
                    horas = (exit_dt - entry_dt).total_seconds() / 3600
                    if t.exit_reason in ("take_profit", "take_profit_2", "trailing_stop"):
                        tp_times.append(horas)
                    elif t.exit_reason == "stop_loss":
                        stop_times.append(horas)
                except Exception:
                    pass

        # V19.0: motivos de perda e ganho
        loss_reasons = {}
        win_reasons = {}
        for t in self._closed_trades:
            reason = t.exit_reason or "unknown"
            if t.status == "LOSS":
                loss_reasons[reason] = loss_reasons.get(reason, 0) + 1
            elif t.status == "WIN":
                win_reasons[reason] = win_reasons.get(reason, 0) + 1

        return {
            "total_trades": total,
            "open_trades": len(self._open_trades),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate": round(win_rate, 4),
            "profit_factor": round(pf, 4),
            "net_profit": round(net_profit, 4),
            "gross_profit": round(gross_profit, 4),
            "gross_loss": round(gross_loss, 4),
            "expectancy": round(expectancy, 4),
            "payoff": round(payoff, 4),
            "sharpe_ratio": round(sharpe, 4),
            "max_drawdown": round(max_dd, 4),
            "max_drawdown_pct": round(max_dd_pct, 6),
            "capital": round(self._capital, 2),
            "total_return_pct": round((self._capital - self._initial_capital) / self._initial_capital * 100, 2),
            "avg_r": round(avg_r, 4) if total > 0 else 0,
            "avg_tp_efficiency": round(avg_tp_eff, 1),
            "partial_tp_pct": round(partial_count / total * 100, 1) if total > 0 else 0,
            "trailing_wins": trailing_wins,
            "break_even_exits": be_exits,
            "avg_tp1_profit_pct": round(avg_tp1_profit, 2),
            "avg_tp2_profit_pct": round(avg_tp2_profit, 2),
            "win_rate_by_classification": win_rate_by_class,
            "win_rate_by_symbol": win_rate_by_symbol,
            "win_rate_by_timeframe": win_rate_by_tf,
            "win_rate_long": round(long_wins / len(long_trades) * 100, 1) if long_trades else 0,
            "win_rate_short": round(short_wins / len(short_trades) * 100, 1) if short_trades else 0,
            "avg_time_to_tp_hours": round(mean(tp_times), 2) if tp_times else 0,
            "avg_time_to_stop_hours": round(mean(stop_times), 2) if stop_times else 0,
            "loss_reasons": loss_reasons,
            "win_reasons": win_reasons,
            "avg_return_pct": round(avg_return, 2),
            "std_return_pct": round(std_returns, 2),
        }

    @property
    def capital(self):
        return self._capital

    @property
    def total_trades(self):
        return len(self._closed_trades)
