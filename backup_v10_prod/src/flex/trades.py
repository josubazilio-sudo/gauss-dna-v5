"""SINAIS TOP — Trade Tracker: winrate, R, exit reasons, drawdown"""

import json
import os
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "state", "trades.json")


def classificar_exit(r):
    if r < -0.2:
        return "stop"
    if r <= 0.2:
        return "be"
    if r < 0.8:
        return "tp1_trail"
    return "tp_final"


class TradeTracker:
    def __init__(self):
        self.wins = 0
        self.losses = 0
        self.total_r = 0.0
        self.trades = []
        self.open_trade = None
        self.peak_r = 0.0
        self.max_dd = 0.0
        self._load()

    def _state_path(self):
        p = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "state"))
        os.makedirs(p, exist_ok=True)
        return os.path.join(p, "trades.json")

    def _load(self):
        path = self._state_path()
        if not os.path.exists(path):
            return
        try:
            with open(path) as f:
                data = json.load(f)
                self.wins = data.get("wins", 0)
                self.losses = data.get("losses", 0)
                self.total_r = data.get("total_r", 0.0)
                self.trades = data.get("trades", [])
                for t in self.trades:
                    if "exit_reason" not in t:
                        t["exit_reason"] = classificar_exit(t.get("r", 0))
                self.open_trade = data.get("open_trade")
                if not data.get("peak_r"):
                    cum_r = 0.0
                    peak = 0.0
                    dd = 0.0
                    for t in self.trades:
                        cum_r += t.get("r", 0)
                        peak = max(peak, cum_r)
                        dd = max(dd, peak - cum_r)
                    self.peak_r = peak
                    self.max_dd = dd
                else:
                    self.peak_r = data.get("peak_r", 0.0)
                    self.max_dd = data.get("max_dd", 0.0)
        except Exception as e:
            logger.warning("Erro ao carregar trades: %s", e)

    def _save(self):
        path = self._state_path()
        try:
            with open(path, "w") as f:
                json.dump({
                    "wins": self.wins,
                    "losses": self.losses,
                    "total_r": self.total_r,
                    "trades": self.trades[-200:],
                    "open_trade": self.open_trade,
                    "peak_r": self.peak_r,
                    "max_dd": self.max_dd,
                }, f)
        except Exception as e:
            logger.warning("Erro ao salvar trades: %s", e)

    def open(self, symbol, direction, preco, stop, tp1, classificacao, score, ticker_last=None):
        if self.open_trade:
            self.close(ticker_last or preco)
        self.open_trade = {
            "symbol": symbol,
            "direction": direction,
            "entry": preco,
            "stop": stop,
            "tp1": tp1,
            "classificacao": classificacao,
            "score": score,
            "time": datetime.now(timezone.utc).isoformat(),
        }
        self._save()

    def close(self, current_price):
        if not self.open_trade:
            return
        t = self.open_trade
        entry = t["entry"]
        direction = t["direction"]
        stop = t["stop"]

        if entry <= 0:
            self.open_trade = None
            return

        if direction == "LONG":
            move_pct = (current_price - entry) / entry
            r_mult = move_pct / abs((entry - stop) / entry) if abs(entry - stop) > 0 else 0
        else:
            move_pct = (entry - current_price) / entry
            r_mult = move_pct / abs((entry - stop) / entry) if abs(entry - stop) > 0 else 0

        r_capped = max(min(r_mult, 3.0), -1.0)
        exit_reason = classificar_exit(r_capped)

        is_win = r_capped > 0
        if is_win:
            self.wins += 1
        else:
            self.losses += 1
        self.total_r += r_capped

        self.peak_r = max(self.peak_r, self.total_r)
        drawdown = self.peak_r - self.total_r
        self.max_dd = max(self.max_dd, drawdown)

        self.trades.append({
            "symbol": t["symbol"],
            "direction": direction,
            "entry": entry,
            "exit": current_price,
            "r": round(r_capped, 2),
            "result": "win" if is_win else "loss",
            "exit_reason": exit_reason,
            "classificacao": t["classificacao"],
            "score": t["score"],
            "open_time": t["time"],
            "close_time": datetime.now(timezone.utc).isoformat(),
        })

        logger.info("Trade fechado: %s %s | R: %.2f | %s | %s",
                     t["symbol"], direction, r_capped,
                     "WIN" if is_win else "LOSS", exit_reason)
        self.open_trade = None
        self._save()

    @property
    def total_trades(self):
        return self.wins + self.losses

    @property
    def winrate(self):
        return round(self.wins / self.total_trades * 100, 1) if self.total_trades > 0 else 0.0

    @property
    def avg_r(self):
        return round(self.total_r / self.total_trades, 2) if self.total_trades > 0 else 0.0

    @property
    def profit_factor(self):
        if self.losses == 0:
            return self.total_r if self.total_r > 0 else 0
        gross_loss = abs(sum(t["r"] for t in self.trades if t["r"] < 0))
        gross_win = sum(t["r"] for t in self.trades if t["r"] > 0)
        return round(gross_win / gross_loss, 2) if gross_loss > 0 else 0

    def get_consecutive_stats(self):
        """Retorna (wins, losses) consecutivas recentes."""
        if not self.trades:
            return 0, 0
        
        wins = 0
        losses = 0
        
        # Verifica a partir do último trade
        for t in reversed(self.trades):
            if t["r"] > 0:
                if losses > 0: break # quebrou a sequência
                wins += 1
            else:
                if wins > 0: break # quebrou a sequência
                losses += 1
        return wins, losses

    @property
    def drawdown_pct(self):
        if self.peak_r <= 0:
            return 0.0
        return round(self.max_dd / abs(self.peak_r) * 100, 1)

    def grade_report(self):
        grades = {"BRONZE": {}, "PRATA": {}, "OURO": {}}
        for grade in grades:
            g_trades = [t for t in self.trades if t.get("classificacao") == grade]
            if not g_trades:
                continue
            wins = sum(1 for t in g_trades if t["r"] > 0)
            losses = len(g_trades) - wins
            total = len(g_trades)
            gross_win = sum(t["r"] for t in g_trades if t["r"] > 0)
            gross_loss = abs(sum(t["r"] for t in g_trades if t["r"] < 0))
            exits = {}
            for t in g_trades:
                er = t.get("exit_reason")
                if not er:
                    er = classificar_exit(t["r"])
                exits.setdefault(er, {"count": 0, "wins": 0, "losses": 0, "total_r": 0.0})
                exits[er]["count"] += 1
                exits[er]["total_r"] += t["r"]
                if t["r"] > 0:
                    exits[er]["wins"] += 1
                else:
                    exits[er]["losses"] += 1
            grades[grade] = {
                "total": total,
                "wins": wins,
                "losses": losses,
                "winrate": round(wins / total * 100, 1) if total > 0 else 0,
                "pf": round(gross_win / gross_loss, 2) if gross_loss > 0 else 0,
                "r_medio": round(sum(t["r"] for t in g_trades) / total, 2) if total > 0 else 0,
                "exits": exits,
            }
        return grades
