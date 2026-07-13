import json
import logging
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from statistics import mean

log = logging.getLogger(__name__)

TRADES_DIR = os.path.join(os.path.dirname(__file__), "trades")


@dataclass
class TradeRecord:
    signal_id: str
    symbol: str
    direction: str
    entry_price: float
    stop_loss: float
    tp1: float
    tp2: float = 0.0
    partial_tp: float = 0.0
    break_even_price: float = 0.0
    atr: float = 0.0
    adx: float = 0.0
    rvol: float = 0.0
    volatility: float = 0.0
    regime: str = ""
    institutional_score: float = 0.0
    consensus: float = 0.0
    confidence: float = 0.0
    quality: float = 0.0
    entry_score: float = 0.0
    entry_time: str = ""
    exit_price: Optional[float] = None
    exit_time: Optional[str] = None
    exit_reason: str = ""
    mfe: float = 0.0
    mae: float = 0.0
    max_profit_before_reversal: float = 0.0
    distance_remaining_to_tp: float = 0.0
    tp_efficiency: float = 0.0
    tp_too_far: bool = False
    partial_filled: bool = False
    trailing_active: bool = False
    r_multiple: float = 0.0
    pnl_percent: float = 0.0
    status: str = "OPEN"


class TradeAnalytics:
    def __init__(self, trades_dir: str = None):
        self._trades_dir = trades_dir or TRADES_DIR
        os.makedirs(self._trades_dir, exist_ok=True)
        self._trades: Dict[str, TradeRecord] = {}
        self._telemetry = {
            "adaptive_tp_used": 0,
            "fallback_tp": 0,
            "scanner_success": 0,
            "scanner_fail": 0,
            "resistance_found": 0,
            "resistance_ignored": 0,
            "partial_tp": 0,
            "trailing_exit": 0,
            "break_even_exit": 0,
            "tp_too_far": 0,
            "total_closed": 0,
        }
        self._load_all()

    def _trade_path(self, signal_id: str) -> str:
        return os.path.join(self._trades_dir, f"{signal_id}.json")

    def _load_all(self):
        if not os.path.isdir(self._trades_dir):
            return
        for fname in os.listdir(self._trades_dir):
            if fname.endswith(".json"):
                path = os.path.join(self._trades_dir, fname)
                try:
                    with open(path) as f:
                        data = json.load(f)
                        rec = TradeRecord(**data)
                        self._trades[rec.signal_id] = rec
                except Exception as e:
                    log.warning(f"TradeAnalytics: erro ao carregar {fname}: {e}")

    def _save(self, rec: TradeRecord):
        path = self._trade_path(rec.signal_id)
        with open(path, "w") as f:
            json.dump(asdict(rec), f, indent=2)

    def record_entry(
        self, signal_id: str, symbol: str, direction: str,
        entry_price: float, stop_loss: float, tp1: float,
        tp2: float = 0.0, partial_tp: float = 0.0,
        break_even_price: float = 0.0,
        atr: float = 0.0, adx: float = 0.0, rvol: float = 0.0,
        volatility: float = 0.0, regime: str = "",
        institutional_score: float = 0.0, consensus: float = 0.0,
        confidence: float = 0.0, quality: float = 0.0,
        entry_score: float = 0.0,
    ) -> TradeRecord:
        rec = TradeRecord(
            signal_id=signal_id, symbol=symbol, direction=direction,
            entry_price=entry_price, stop_loss=stop_loss, tp1=tp1,
            tp2=tp2, partial_tp=partial_tp,
            break_even_price=break_even_price or entry_price,
            atr=atr, adx=adx, rvol=rvol, volatility=volatility,
            regime=regime, institutional_score=institutional_score,
            consensus=consensus, confidence=confidence, quality=quality,
            entry_score=entry_score,
            entry_time=datetime.now(timezone.utc).isoformat(),
        )
        self._trades[signal_id] = rec
        self._save(rec)
        return rec

    def record_exit(
        self, signal_id: str, exit_price: float, exit_reason: str,
        mfe: float = 0.0, mae: float = 0.0,
        max_profit_before_reversal: float = 0.0,
        r_multiple: float = 0.0, pnl_percent: float = 0.0,
        partial_filled: bool = False, trailing_active: bool = False,
    ):
        rec = self._trades.get(signal_id)
        if not rec:
            log.warning(f"TradeAnalytics: trade {signal_id} nao encontrado")
            return
        rec.exit_price = exit_price
        rec.exit_time = datetime.now(timezone.utc).isoformat()
        rec.exit_reason = exit_reason
        rec.mfe = mfe
        rec.mae = mae
        rec.max_profit_before_reversal = max_profit_before_reversal
        rec.r_multiple = r_multiple
        rec.pnl_percent = pnl_percent
        rec.partial_filled = partial_filled
        rec.trailing_active = trailing_active
        rec.status = "WIN" if pnl_percent > 0 else ("LOSS" if pnl_percent < 0 else "BREAK_EVEN")

        rec.tp_efficiency = self.compute_tp_efficiency(
            max_reached=max_profit_before_reversal,
            tp_proposed=rec.tp1,
            entry=rec.entry_price,
            direction=rec.direction,
        )

        max_price = rec.entry_price
        if rec.direction.upper() in ("LONG", "BUY"):
            max_price = rec.entry_price * (1 + max_profit_before_reversal / 100)
        elif max_profit_before_reversal > 0:
            max_price = rec.entry_price * (1 - max_profit_before_reversal / 100)

        rec.tp_too_far = self.detect_tp_too_far(
            max_price=max_price,
            entry=rec.entry_price,
            tp1=rec.tp1,
            direction=rec.direction,
        )

        tp_range = abs(rec.tp1 - rec.entry_price)
        rec.distance_remaining_to_tp = (
            abs(rec.tp1 - exit_price) / tp_range * 100 if tp_range > 0 else 0
        )

        self._telemetry["total_closed"] += 1
        if partial_filled:
            self._telemetry["partial_tp"] += 1
        if trailing_active and exit_reason == "trailing_stop":
            self._telemetry["trailing_exit"] += 1
        if exit_reason == "stop_loss" and exit_price and rec.break_even_price > 0 and abs(exit_price - rec.break_even_price) / rec.break_even_price < 0.001:
            self._telemetry["break_even_exit"] += 1
        if rec.tp_too_far:
            self._telemetry["tp_too_far"] += 1

        self._save(rec)

    @staticmethod
    def compute_tp_efficiency(
        max_reached: float, tp_proposed: float, entry: float, direction: str,
    ) -> float:
        if tp_proposed <= 0 or entry <= 0:
            return 0.0
        is_long = direction.upper() in ("LONG", "BUY")
        if is_long:
            max_pct = (max_reached - entry) / entry * 100 if max_reached > entry else 0
            tp_pct = (tp_proposed - entry) / entry * 100
        else:
            max_pct = (entry - max_reached) / entry * 100 if max_reached < entry else 0
            tp_pct = (entry - tp_proposed) / entry * 100
        if tp_pct <= 0:
            return 0.0
        return round(min(max_pct / tp_pct * 100, 100.0), 1)

    @staticmethod
    def detect_tp_too_far(max_price: float, entry: float, tp1: float, direction: str) -> bool:
        if tp1 == entry:
            return False
        is_long = direction.upper() in ("LONG", "BUY")
        if is_long:
            progress = (max_price - entry) / (tp1 - entry) * 100 if tp1 > entry else 0
        else:
            progress = (entry - max_price) / (entry - tp1) * 100 if entry > tp1 else 0
        return progress >= 90.0

    def get_trade(self, signal_id: str) -> Optional[TradeRecord]:
        return self._trades.get(signal_id)

    def get_stats(self) -> Dict:
        closed = [t for t in self._trades.values() if t.status != "OPEN"]
        if not closed:
            return {"status": "no_trades", "total_trades": 0}

        wins = [t for t in closed if t.status == "WIN"]
        losses = [t for t in closed if t.status == "LOSS"]

        tp_effs = [t.tp_efficiency for t in closed if t.tp_efficiency > 0]
        avg_tp_eff = mean(tp_effs) if tp_effs else 0

        partial_count = sum(1 for t in closed if t.partial_filled)
        trailing_wins = sum(1 for t in wins if t.trailing_active)
        tp_too_far_count = sum(1 for t in closed if t.tp_too_far)
        avg_r = mean([t.r_multiple for t in closed if t.r_multiple != 0]) if closed else 0

        tp1_wins = [t for t in wins if t.exit_reason in ("take_profit", "trailing_stop")]
        tp2_wins = [t for t in wins if t.exit_reason == "take_profit_2"]

        avg_tp1 = mean([t.pnl_percent for t in tp1_wins]) if tp1_wins else 0
        avg_tp2 = mean([t.pnl_percent for t in tp2_wins]) if tp2_wins else 0

        return {
            "total_trades": len(closed),
            "avg_tp_efficiency": round(avg_tp_eff, 1),
            "tp_efficiency_classification": self._classify_efficiency(avg_tp_eff),
            "partial_tp_pct": round(partial_count / len(closed) * 100, 1) if closed else 0,
            "trailing_wins": trailing_wins,
            "tp_too_far_count": tp_too_far_count,
            "avg_r_multiple": round(avg_r, 4),
            "avg_tp1_profit_pct": round(avg_tp1, 2),
            "avg_tp2_profit_pct": round(avg_tp2, 2),
        }

    @staticmethod
    def _classify_efficiency(eff: float) -> str:
        if eff >= 95:
            return "Excelente"
        elif eff >= 85:
            return "Boa"
        elif eff >= 70:
            return "Media"
        return "Ruim"

    def get_telemetry(self) -> Dict:
        return dict(self._telemetry)

    def increment_telemetry(self, key: str, count: int = 1):
        if key in self._telemetry:
            self._telemetry[key] += count

    def generate_learning_report(self) -> Optional[Dict]:
        closed = [t for t in self._trades.values() if t.status != "OPEN"]
        if len(closed) < 300:
            return None

        wins = [t for t in closed if t.status == "WIN"]

        atr_wins = [t.atr for t in wins if t.atr > 0]
        ideal_atr = mean(atr_wins) if atr_wins else 0

        trailing_dists = []
        for t in wins:
            if t.trailing_active and t.exit_price and t.entry_price:
                dist = abs(t.exit_price - t.entry_price) / t.entry_price * 100
                trailing_dists.append(dist)
        ideal_trailing = mean(trailing_dists) if trailing_dists else 0

        partial_wins = sum(1 for t in wins if t.partial_filled)
        ideal_partial_pct = partial_wins / len(wins) * 100 if wins else 0

        mfe_values = [t.mfe for t in wins if t.mfe > 0]
        ideal_tp_distance = mean(mfe_values) if mfe_values else 0

        half = len(closed) // 2
        first_half = closed[:half]
        second_half = closed[half:]

        def _metrics(trades):
            w = [t for t in trades if t.status == "WIN"]
            l = [t for t in trades if t.status == "LOSS"]
            wr = len(w) / len(trades) if trades else 0
            gp = sum(t.r_multiple for t in w)
            gl = abs(sum(t.r_multiple for t in l))
            pf = gp / gl if gl > 0 else gp
            return wr, pf

        wr1, pf1 = _metrics(first_half)
        wr2, pf2 = _metrics(second_half)

        return {
            "total_trades": len(closed),
            "wins": len(wins),
            "antes": {"win_rate": round(wr1, 4), "profit_factor": round(pf1, 4)},
            "depois": {"win_rate": round(wr2, 4), "profit_factor": round(pf2, 4)},
            "sugestoes": {
                "atr_ideal": round(ideal_atr, 4),
                "trailing_distancia_ideal_pct": round(ideal_trailing, 2),
                "partial_ideal_pct": round(ideal_partial_pct, 1),
                "tp_distancia_ideal_mfe_medio_pct": round(ideal_tp_distance, 2),
            },
            "expectativa_mudanca": {
                "win_rate_delta": round((wr2 - wr1) * 100, 2),
                "profit_factor_delta": round(pf2 - pf1, 4),
            },
        }
