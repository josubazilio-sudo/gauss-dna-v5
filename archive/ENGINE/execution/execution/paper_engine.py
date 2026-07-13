import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

log = logging.getLogger(__name__)


class PaperPosition:
    def __init__(self, symbol: str, direction: str, entry: float,
                 quantity: float, stop: float, tp1: float, tp2: float,
                 leverage: int = 1, score: int = 0, grade: str = "",
                 signal_id: str = ""):
        self.symbol = symbol
        self.direction = direction
        self.entry = entry
        self.quantity = quantity
        self.stop = stop
        self.tp1 = tp1
        self.tp2 = tp2
        self.leverage = leverage
        self.score = score
        self.grade = grade
        self.signal_id = signal_id
        self.current_price = entry
        self.open_time = datetime.now(timezone.utc)
        self.unrealized_pnl = 0.0
        self.realized_pnl = 0.0
        self.highest_price = entry
        self.lowest_price = entry
        self.tp1_hit = False
        self.stopped_out = False
        self.breakeven_set = False

    @property
    def pnl_pct(self):
        if self.entry <= 0:
            return 0.0
        if self.direction == "LONG":
            return ((self.current_price - self.entry) / self.entry) * self.leverage * 100
        return ((self.entry - self.current_price) / self.entry) * self.leverage * 100

    @property
    def r_multiple(self):
        if self.entry <= 0 or abs(self.entry - self.stop) <= 0:
            return 0.0
        risk_pct = abs(self.entry - self.stop) / self.entry
        if risk_pct <= 0:
            return 0.0
        if self.direction == "LONG":
            return (self.current_price - self.entry) / (self.entry * risk_pct)
        return (self.entry - self.current_price) / (self.entry * risk_pct)

    def update_price(self, price: float):
        self.current_price = price
        if self.direction == "LONG":
            self.unrealized_pnl = (price - self.entry) * self.quantity
            self.highest_price = max(self.highest_price, price)
        else:
            self.unrealized_pnl = (self.entry - price) * self.quantity
            self.lowest_price = min(self.lowest_price, price)

    def check_stop(self):
        if self.stopped_out:
            return True
        if self.direction == "LONG" and self.current_price <= self.stop:
            self.stopped_out = True
            self.realized_pnl = self.unrealized_pnl
            return True
        if self.direction == "SHORT" and self.current_price >= self.stop:
            self.stopped_out = True
            self.realized_pnl = self.unrealized_pnl
            return True
        return False

    def check_tp1(self):
        if self.tp1_hit:
            return True
        if self.direction == "LONG" and self.current_price >= self.tp1:
            self.tp1_hit = True
            return True
        if self.direction == "SHORT" and self.current_price <= self.tp1:
            self.tp1_hit = True
            return True
        return False


class PaperEngine:
    def __init__(self, initial_balance: float = 100.0):
        self.balance = initial_balance
        self.positions: Dict[str, PaperPosition] = {}
        self.closed_trades: List[Dict] = []
        self.peak_balance = initial_balance
        self.max_drawdown = 0.0

    def _key(self, symbol: str, direction: str) -> str:
        return f"{symbol}_{direction}"

    def open(self, symbol: str, direction: str, entry: float,
             stop: float, tp1: float, tp2: float, quantity: float,
             leverage: int = 1, score: int = 0, grade: str = "",
             signal_id: str = "") -> bool:
        key = self._key(symbol, direction)
        if key in self.positions:
            log.warning("Paper: already have position %s — closing first", key)
            self.close(key, entry, "replaced")

        margin = (entry * quantity) / leverage
        if margin > self.balance:
            log.warning("Paper: insufficient balance for %s (%.2f < %.2f)",
                        symbol, self.balance, margin)
            return False
        pos = PaperPosition(symbol, direction, entry, quantity, stop, tp1, tp2,
                            leverage, score, grade, signal_id)
        self.positions[key] = pos
        self.balance -= margin
        log.info("[PAPER] OPEN %s %s | Size: %.4f | Entry: %.8f | Score: %d",
                 symbol, direction, quantity, entry, score)
        return True

    def close(self, key: str, price: float, reason: str = "manual") -> Optional[Dict]:
        pos = self.positions.pop(key, None)
        if pos is None:
            return None

        if pos.direction == "LONG":
            pnl = (price - pos.entry) * pos.quantity
        else:
            pnl = (pos.entry - price) * pos.quantity

        self.balance += (pos.entry * pos.quantity) / pos.leverage + pnl
        self.peak_balance = max(self.peak_balance, self.balance)
        dd = ((self.peak_balance - self.balance) / self.peak_balance * 100) if self.peak_balance > 0 else 0
        self.max_drawdown = max(self.max_drawdown, dd)

        risk_pct = abs(pos.entry - pos.stop) / pos.entry if pos.entry > 0 else 0.01
        r = pnl / (pos.entry * pos.quantity * risk_pct) if risk_pct > 0 and pos.quantity > 0 else 0

        trade = {
            "symbol": pos.symbol,
            "direction": pos.direction,
            "entry": pos.entry,
            "exit": price,
            "quantity": pos.quantity,
            "pnl": round(pnl, 2),
            "r": round(r, 2),
            "result": "win" if pnl > 0 else "loss",
            "reason": reason,
            "score": pos.score,
            "grade": pos.grade,
            "signal_id": pos.signal_id,
            "open_time": pos.open_time.isoformat(),
            "close_time": datetime.now(timezone.utc).isoformat(),
        }
        self.closed_trades.append(trade)
        log.info("[PAPER] CLOSE %s %s | PnL: %.2f | R: %.2f | %s",
                 pos.symbol, pos.direction, pnl, r, reason)
        return trade

    def update_price(self, symbol: str, price: float):
        for pos in self.positions.values():
            if pos.symbol == symbol:
                pos.update_price(price)

    def check_positions(self) -> List[Dict]:
        closed = []
        for key in list(self.positions.keys()):
            pos = self.positions.get(key)
            if pos is None:
                continue

            if pos.check_stop():
                t = self.close(key, pos.stop, "stop_loss")
                if t:
                    closed.append(t)
                continue

            if pos.check_tp1() and not pos.breakeven_set:
                pos.breakeven_set = True
                be = pos.entry * 1.001 if pos.direction == "LONG" else pos.entry * 0.999
                pos.stop = be
                log.info("[PAPER] %s moved to break-even", pos.symbol)

            if pos.breakeven_set:
                if pos.direction == "LONG" and pos.current_price >= pos.tp2:
                    t = self.close(key, pos.tp2, "tp2_target")
                    if t:
                        closed.append(t)
                elif pos.direction == "SHORT" and pos.current_price <= pos.tp2:
                    t = self.close(key, pos.tp2, "tp2_target")
                    if t:
                        closed.append(t)

        return closed

    def get_open_positions(self) -> List[Dict]:
        return [{
            "symbol": p.symbol,
            "direction": p.direction,
            "entry": p.entry,
            "current": p.current_price,
            "stop": p.stop,
            "tp1": p.tp1,
            "tp2": p.tp2,
            "quantity": p.quantity,
            "unrealized_pnl": round(p.unrealized_pnl, 2),
            "pnl_pct": round(p.pnl_pct, 2),
            "r": round(p.r_multiple, 2),
            "score": p.score,
            "grade": p.grade,
            "leverage": p.leverage,
        } for p in self.positions.values()]

    def get_stats(self):
        wins = sum(1 for t in self.closed_trades if t["pnl"] > 0)
        losses = len(self.closed_trades) - wins
        total_pnl = sum(t["pnl"] for t in self.closed_trades)
        total_r = sum(t["r"] for t in self.closed_trades)
        return {
            "balance": round(self.balance, 2),
            "equity": round(self.balance + sum(p.unrealized_pnl for p in self.positions.values()), 2),
            "open_positions": len(self.positions),
            "total_trades": len(self.closed_trades),
            "wins": wins,
            "losses": losses,
            "winrate": round(wins / max(len(self.closed_trades), 1) * 100, 1),
            "total_pnl": round(total_pnl, 2),
            "total_r": round(total_r, 2),
            "avg_r": round(total_r / max(len(self.closed_trades), 1), 2),
            "max_drawdown": round(self.max_drawdown, 1),
        }
