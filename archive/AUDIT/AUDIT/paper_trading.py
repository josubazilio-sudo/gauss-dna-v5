import logging
import csv
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .backtest_audit import TradeRecord

log = logging.getLogger(__name__)

PAPER_DIR = Path(__file__).parent / "data" / "paper"


@dataclass
class PaperTrade:
    timestamp: str
    pair: str
    timeframe: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    executed_price: float = 0.0
    slippage_pct: float = 0.0
    spread_pct: float = 0.0
    result: str = ""
    profit_loss_pct: float = 0.0
    duration_min: float = 0.0
    close_reason: str = ""
    exit_price: float = 0.0
    backtest_pnl: float = 0.0
    deviation_pct: float = 0.0


class PaperTradingEngine:
    def __init__(self):
        self._dir = PAPER_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._trades: List[PaperTrade] = []

    def execute_signal(self, pair: str, tf: str, direction: str,
                       entry: float, sl: float, tp1: float, tp2: float,
                       backtest_pnl: float = 0.0,
                       current_spread: float = 0.0005) -> PaperTrade:
        slippage = entry * current_spread * 0.5
        executed = entry + slippage if direction == "long" else entry - slippage

        trade = PaperTrade(
            timestamp=datetime.now(timezone.utc).isoformat(),
            pair=pair, timeframe=tf, direction=direction,
            entry_price=entry, stop_loss=sl,
            take_profit_1=tp1, take_profit_2=tp2,
            executed_price=round(executed, 2),
            slippage_pct=round(abs(executed - entry) / entry, 6),
            spread_pct=current_spread,
            backtest_pnl=backtest_pnl,
        )
        self._trades.append(trade)
        return trade

    def close_trade(self, trade: PaperTrade, result: str,
                    exit_price: float, reason: str = "") -> None:
        trade.result = result
        trade.exit_price = exit_price
        trade.close_reason = reason

        if trade.direction == "long":
            trade.profit_loss_pct = (exit_price - trade.executed_price) / trade.executed_price
        else:
            trade.profit_loss_pct = (trade.executed_price - exit_price) / trade.executed_price

        if trade.backtest_pnl != 0:
            trade.deviation_pct = abs(trade.profit_loss_pct - trade.backtest_pnl) / abs(trade.backtest_pnl)

    def save(self) -> None:
        path = self._dir / "paper_trades.json"
        existing = []
        if path.exists():
            try:
                with open(path, "r") as f:
                    existing = json.load(f)
            except Exception:
                pass
        records = [asdict(t) for t in self._trades]
        all_records = existing + records
        with open(path, "w") as f:
            json.dump(all_records, f, indent=2)

        csv_path = self._dir / "paper_trades.csv"
        mode = "a" if csv_path.exists() else "w"
        with open(csv_path, mode, newline="") as f:
            if self._trades:
                writer = csv.DictWriter(f, fieldnames=asdict(self._trades[0]).keys())
                if mode == "w":
                    writer.writeheader()
                for t in records:
                    writer.writerow(t)

        log.info("PaperTrading: saved %d trades", len(self._trades))
        self._trades.clear()

    def compare_with_backtest(self, backtest_trades: List[TradeRecord]) -> Dict[str, Any]:
        if not backtest_trades or not self._trades:
            return {"error": "Dados insuficientes para comparação"}

        bt_wr = sum(1 for t in backtest_trades if t.result == "win") / len(backtest_trades) if backtest_trades else 0
        pt_wr = sum(1 for t in self._trades if t.result == "win") / len(self._trades) if self._trades else 0

        bt_pf = (
            sum(abs(t.profit_loss_pct) for t in backtest_trades if t.result == "win") /
            sum(abs(t.profit_loss_pct) for t in backtest_trades if t.result == "loss")
            if sum(1 for t in backtest_trades if t.result == "loss") > 0 else 0
        )
        pt_pf = (
            sum(abs(t.profit_loss_pct) for t in self._trades if t.result == "win") /
            sum(abs(t.profit_loss_pct) for t in self._trades if t.result == "loss")
            if sum(1 for t in self._trades if t.result == "loss") > 0 else 0
        )

        return {
            "backtest_trades": len(backtest_trades),
            "paper_trades": len(self._trades),
            "backtest_win_rate": round(bt_wr, 4),
            "paper_win_rate": round(pt_wr, 4),
            "backtest_profit_factor": round(bt_pf, 4),
            "paper_profit_factor": round(pt_pf, 4),
            "wr_deviation": round(abs(bt_wr - pt_wr), 4),
            "pf_deviation": round(abs(bt_pf - pt_pf), 4) if bt_pf > 0 else 0,
        }

    def load_paper_trades(self) -> List[Dict]:
        path = self._dir / "paper_trades.json"
        if path.exists():
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except Exception:
                return []
        return []
