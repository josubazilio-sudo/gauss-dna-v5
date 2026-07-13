import json
import logging
import os
import sqlite3
import uuid
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple

log = logging.getLogger(__name__)

DB_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "MEMORY", "trades",
)
DB_PATH = os.path.join(DB_DIR, "trades.db")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS trades (
    id              TEXT PRIMARY KEY,
    signal_id       TEXT UNIQUE,
    opened_at       TEXT NOT NULL,
    closed_at       TEXT,
    asset           TEXT NOT NULL,
    timeframe       TEXT NOT NULL,
    direction       TEXT NOT NULL,
    entry_price     REAL NOT NULL,
    stop_loss       REAL NOT NULL,
    take_profit_1   REAL,
    take_profit_2   REAL,
    quality         REAL,
    confidence      REAL,
    overall_score   REAL,
    consensus       REAL,
    conviction      TEXT,
    expectancy      TEXT,
    trend           TEXT,
    kalman          TEXT,
    classification  TEXT,
    risk_reward     REAL,
    leverage        INTEGER,
    account_size    REAL,
    capital_per_trade REAL,
    collateral      REAL,
    position_value  REAL,
    profit_est      REAL,
    loss_est        REAL,
    resultado       TEXT,
    exit_price      REAL,
    time_to_tp1     REAL,
    time_to_stop    REAL,
    lucro_usdt      REAL,
    perda_usdt      REAL,
    retorno_pct     REAL,
    mae             REAL,
    mfe             REAL,
    setup_key       TEXT,
    r_multiple      REAL,
    cycle           INTEGER,
    entry_id        TEXT
);

CREATE TABLE IF NOT EXISTS market_data (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id TEXT NOT NULL REFERENCES trades(id),
    recorded_at TEXT NOT NULL,
    price   REAL NOT NULL,
    high    REAL,
    low     REAL
);

CREATE INDEX IF NOT EXISTS idx_trades_signal_id ON trades(signal_id);
CREATE INDEX IF NOT EXISTS idx_trades_asset ON trades(asset);
CREATE INDEX IF NOT EXISTS idx_trades_timeframe ON trades(timeframe);
CREATE INDEX IF NOT EXISTS idx_trades_direction ON trades(direction);
CREATE INDEX IF NOT EXISTS idx_trades_classification ON trades(classification);
CREATE INDEX IF NOT EXISTS idx_trades_setup_key ON trades(setup_key);
CREATE INDEX IF NOT EXISTS idx_trades_resultado ON trades(resultado);
CREATE INDEX IF NOT EXISTS idx_trades_opened_at ON trades(opened_at);
"""


def _make_setup_key(trend: str, kalman: str) -> str:
    t = trend.upper().replace(" ", "_") if trend else "UNKNOWN"
    k = kalman.upper().replace(" ", "_") if kalman else "UNKNOWN"
    return f"Trend_{t}+Kalman_{k}"


class TradeRegistry:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or DB_PATH
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()
        self._cache: Optional[Dict] = None

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript(SCHEMA_SQL)

    # --- OPEN / CLOSE TRADES -----------------------------------------------

    def open_trade(self, signal_data: dict) -> str:
        trade_id = str(uuid.uuid4())[:12]
        now = datetime.now(timezone.utc).isoformat()

        asset = signal_data.get("symbol", signal_data.get("asset", "???"))
        timeframe = signal_data.get("timeframe", "???")
        direction = signal_data.get("direction", "UNKNOWN").upper()
        entry_price = float(signal_data.get("entry_price", 0))
        stop_loss = float(signal_data.get("stop_loss", 0))
        tp1 = float(signal_data.get("take_profit_1", 0))
        tp2 = float(signal_data.get("take_profit_2", 0))
        quality = signal_data.get("quality_score", signal_data.get("quality", 0))
        confidence = signal_data.get("confidence_score", signal_data.get("confidence", 0))
        overall = signal_data.get("overall_score_value", 0)
        consensus = signal_data.get("consensus_score", signal_data.get("consensus", 0))
        conviction = signal_data.get("conviction_level", "")
        expectancy = signal_data.get("expectancy_level", "")
        trend = signal_data.get("trend", "")
        kalman = signal_data.get("kalman_direction", "")
        classification = signal_data.get("classification_label", "")
        rr = float(signal_data.get("risk_reward", 0))
        cycle = signal_data.get("cycle_id", 0)

        ops = signal_data.get("operational", {})
        if not ops:
            # BUG FIX: assinatura de OperationalCalculator.calculate() e
            # (entry_price, stop_loss, take_profit_1, quantity, balance,
            # leverage=1.0) — a chamada anterior passava (quality,
            # entry_price, stop_loss, tp1), causando
            # "missing 1 required positional argument: 'balance'"
            # sempre que este fallback era atingido.
            from ENGINE.common.operational import OperationalCalculator
            calc = OperationalCalculator()
            fallback_balance = float(signal_data.get("balance", 0) or 0)
            fallback_leverage = float(signal_data.get("leverage", 1) or 1)
            ops = calc.calculate(
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit_1=tp1,
                quantity=float(signal_data.get("quantity", 0) or 0),
                balance=fallback_balance,
                leverage=fallback_leverage,
            )
            # BUG FIX: OperationalCalculator.calculate() nao retorna mais
            # leverage/account_size/capital_per_trade/collateral/
            # position_value/profit_est/loss_est (schema antigo) — mapeia
            # para as chaves reais (valor_nominal, margem_utilizada_usdt,
            # lucro_liquido_usdt, perda_maxima_usdt, alavancagem_efetiva).
            ops.setdefault("leverage", ops.get("alavancagem_efetiva", fallback_leverage))
            ops.setdefault("account_size", fallback_balance)
            ops.setdefault("capital_per_trade", ops.get("margem_utilizada_usdt", 0))
            ops.setdefault("collateral", ops.get("margem_utilizada_usdt", 0))
            ops.setdefault("position_value", ops.get("valor_nominal", 0))
            ops.setdefault("profit_est", ops.get("lucro_liquido_usdt", 0))
            ops.setdefault("loss_est", ops.get("perda_maxima_usdt", 0))

        leverage = int(ops.get("leverage", 1))
        account_size = float(ops.get("account_size", 200))
        capital_pt = float(ops.get("capital_per_trade", 0))
        collateral = float(ops.get("collateral", 0))
        pos_value = float(ops.get("position_value", 0))
        profit_est = float(ops.get("profit_est", 0))
        loss_est = float(ops.get("loss_est", 0))

        signal_id = signal_data.get("signal_id", signal_data.get("trace_id", f"sig_{trade_id}"))
        setup_key = _make_setup_key(trend, kalman)

        with self._conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO trades
                (id, signal_id, opened_at, asset, timeframe, direction,
                 entry_price, stop_loss, take_profit_1, take_profit_2,
                 quality, confidence, overall_score, consensus,
                 conviction, expectancy, trend, kalman, classification,
                 risk_reward, leverage, account_size, capital_per_trade,
                 collateral, position_value, profit_est, loss_est,
                 setup_key, cycle, entry_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                trade_id, signal_id, now, asset, timeframe, direction,
                entry_price, stop_loss, tp1, tp2 if tp2 > 0 else None,
                quality, confidence, overall, consensus,
                conviction, expectancy, trend, kalman, classification,
                rr, leverage, account_size, capital_pt,
                collateral, pos_value, profit_est, loss_est,
                setup_key, cycle, trade_id,
            ))

        log.info("TradeRegistry OPEN: %s %s %s @ %.4f (id=%s)", asset, timeframe, direction, entry_price, trade_id)
        return trade_id

    def close_trade(self, signal_id: str, resultado: str,
                    exit_price: float = 0.0,
                    time_to_tp1: float = 0.0,
                    time_to_stop: float = 0.0,
                    lucro_usdt: float = 0.0,
                    perda_usdt: float = 0.0,
                    retorno_pct: float = 0.0,
                    mae: float = 0.0,
                    mfe: float = 0.0,
                    r_multiple: float = 0.0) -> bool:
        now = datetime.now(timezone.utc).isoformat()

        with self._conn() as conn:
            cur = conn.execute("SELECT id, entry_price FROM trades WHERE signal_id=? AND resultado IS NULL", (signal_id,))
            row = cur.fetchone()
            if not row:
                log.warning("TradeRegistry: no open trade found for signal_id=%s", signal_id)
                return False

            trade_id = row["id"]

            conn.execute("""
                UPDATE trades SET
                    resultado=?, closed_at=?, exit_price=?,
                    time_to_tp1=?, time_to_stop=?,
                    lucro_usdt=?, perda_usdt=?, retorno_pct=?,
                    mae=?, mfe=?, r_multiple=?
                WHERE id=?
            """, (
                resultado, now, exit_price if exit_price > 0 else None,
                time_to_tp1, time_to_stop,
                lucro_usdt, perda_usdt, retorno_pct,
                mae, mfe, r_multiple,
                trade_id,
            ))

        log.info("TradeRegistry CLOSE: %s -> %s (PnL=%.2fUSDT %.2f%%)", signal_id, resultado, lucro_usdt, retorno_pct)
        return True

    # --- QUERIES -----------------------------------------------------------

    def get_open_trades(self) -> List[Dict]:
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM trades WHERE resultado IS NULL ORDER BY opened_at DESC").fetchall()
            return [dict(r) for r in rows]

    def get_closed_trades(self, days: int = None) -> List[Dict]:
        with self._conn() as conn:
            if days:
                cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
                rows = conn.execute(
                    "SELECT * FROM trades WHERE resultado IS NOT NULL AND opened_at >= ? ORDER BY closed_at DESC",
                    (cutoff,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM trades WHERE resultado IS NOT NULL ORDER BY closed_at DESC").fetchall()
            return [dict(r) for r in rows]

    def get_trade_by_signal_id(self, signal_id: str) -> Optional[Dict]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM trades WHERE signal_id=?", (signal_id,)).fetchone()
            return dict(row) if row else None

    # --- STATISTICS --------------------------------------------------------

    def get_statistics(self) -> Dict:
        trades = self.get_closed_trades()
        if not trades:
            return {"status": "no_trades", "total_trades": 0}

        wins = [t for t in trades if t.get("resultado") == "WIN"]
        losses = [t for t in trades if t.get("resultado") == "LOSS"]
        be = [t for t in trades if t.get("resultado") == "BREAKEVEN"]
        total = len(trades)

        win_rate = len(wins) / total * 100 if total > 0 else 0.0
        gross_profit = sum(t.get("lucro_usdt", 0) or 0 for t in wins)
        gross_loss = sum(abs(t.get("perda_usdt", 0) or 0) for t in losses)
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else (
            None if gross_profit == 0 else float("inf")
        )

        avg_win = gross_profit / len(wins) if wins else 0.0
        avg_loss = gross_loss / len(losses) if losses else 0.0
        expectancy = avg_win * (win_rate / 100) - abs(avg_loss) * (1 - win_rate / 100)

        payoff = avg_win / abs(avg_loss) if avg_loss != 0 else 0.0

        equity = 0.0
        peak = 0.0
        drawdown = 0.0
        for t in trades:
            pnl = (t.get("lucro_usdt", 0) or 0) - (t.get("perda_usdt", 0) or 0)
            equity += pnl
            if equity > peak:
                peak = equity
            dd = peak - equity
            if dd > drawdown:
                drawdown = dd

        qual_scores = [t.get("quality", 0) or 0 for t in trades if t.get("quality")]
        conf_scores = [t.get("confidence", 0) or 0 for t in trades if t.get("confidence")]
        overall_scores = [t.get("overall_score", 0) or 0 for t in trades if t.get("overall_score")]
        cons_scores = [t.get("consensus", 0) or 0 for t in trades if t.get("consensus")]
        rr_vals = [t.get("risk_reward", 0) or 0 for t in trades if t.get("risk_reward")]

        def safe_avg(vals):
            return round(sum(vals) / len(vals), 4) if vals else 0.0

        return {
            "total_trades": total,
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "breakeven_trades": len(be),
            "win_rate": round(win_rate, 2),
            "profit_factor": round(profit_factor, 2) if profit_factor is not None else None,
            "drawdown": round(drawdown, 2),
            "payoff": round(payoff, 2),
            "expectancy": round(expectancy, 2),
            "avg_quality": safe_avg(qual_scores),
            "avg_confidence": safe_avg(conf_scores),
            "avg_overall_score": safe_avg(overall_scores),
            "avg_consensus": safe_avg(cons_scores),
            "avg_rr": safe_avg(rr_vals),
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
            "net_pnl": round(gross_profit - gross_loss, 2),
            "payoff_ratio": round(payoff, 2),
        }

    def get_statistics_by_classification(self) -> Dict[str, Dict]:
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT classification,
                       COUNT(*) as total,
                       SUM(CASE WHEN resultado='WIN' THEN 1 ELSE 0 END) as wins,
                       SUM(CASE WHEN resultado='LOSS' THEN 1 ELSE 0 END) as losses,
                       SUM(CASE WHEN resultado='BREAKEVEN' THEN 1 ELSE 0 END) as be,
                       AVG(lucro_usdt) as avg_lucro,
                       AVG(perda_usdt) as avg_perda,
                       AVG(retorno_pct) as avg_retorno,
                       AVG(overall_score) as avg_overall
                FROM trades
                WHERE resultado IS NOT NULL
                GROUP BY classification
                ORDER BY wins DESC
            """).fetchall()

        result = {}
        for r in rows:
            total = r["total"]
            wins = r["wins"]
            losses = r["losses"]
            wr = wins / total * 100 if total > 0 else 0.0
            result[r["classification"] or "N/A"] = {
                "total": total,
                "wins": wins,
                "losses": losses,
                "breakeven": r["be"],
                "win_rate": round(wr, 2),
                "avg_retorno_pct": round(r["avg_retorno"] or 0, 2),
                "avg_overall": round(r["avg_overall"] or 0, 1),
            }
        return result

    def get_statistics_by_timeframe(self) -> Dict[str, Dict]:
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT timeframe,
                       COUNT(*) as total,
                       SUM(CASE WHEN resultado='WIN' THEN 1 ELSE 0 END) as wins,
                       SUM(CASE WHEN resultado='LOSS' THEN 1 ELSE 0 END) as losses,
                       SUM(CASE WHEN resultado='BREAKEVEN' THEN 1 ELSE 0 END) as be,
                       AVG(retorno_pct) as avg_retorno
                FROM trades
                WHERE resultado IS NOT NULL
                GROUP BY timeframe
                ORDER BY wins DESC
            """).fetchall()

        result = {}
        for r in rows:
            total = r["total"]
            wins = r["wins"]
            losses = r["losses"]
            wr = wins / total * 100 if total > 0 else 0.0
            result[r["timeframe"] or "N/A"] = {
                "total": total,
                "wins": wins,
                "losses": losses,
                "breakeven": r["be"],
                "win_rate": round(wr, 2),
                "avg_retorno_pct": round(r["avg_retorno"] or 0, 2),
            }
        return result

    def get_statistics_by_direction(self) -> Dict[str, Dict]:
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT direction,
                       COUNT(*) as total,
                       SUM(CASE WHEN resultado='WIN' THEN 1 ELSE 0 END) as wins,
                       SUM(CASE WHEN resultado='LOSS' THEN 1 ELSE 0 END) as losses,
                       SUM(CASE WHEN resultado='BREAKEVEN' THEN 1 ELSE 0 END) as be,
                       AVG(retorno_pct) as avg_retorno
                FROM trades
                WHERE resultado IS NOT NULL
                GROUP BY direction
                ORDER BY wins DESC
            """).fetchall()

        result = {}
        for r in rows:
            total = r["total"]
            wins = r["wins"]
            losses = r["losses"]
            wr = wins / total * 100 if total > 0 else 0.0
            result[r["direction"] or "N/A"] = {
                "total": total,
                "wins": wins,
                "losses": losses,
                "breakeven": r["be"],
                "win_rate": round(wr, 2),
                "avg_retorno_pct": round(r["avg_retorno"] or 0, 2),
            }
        return result

    # --- SETUP RANKING -----------------------------------------------------

    def get_setup_ranking(self, min_trades: int = 1) -> List[Dict]:
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT setup_key,
                       COUNT(*) as total,
                       SUM(CASE WHEN resultado='WIN' THEN 1 ELSE 0 END) as wins,
                       SUM(CASE WHEN resultado='LOSS' THEN 1 ELSE 0 END) as losses,
                       SUM(CASE WHEN resultado='BREAKEVEN' THEN 1 ELSE 0 END) as be,
                       AVG(retorno_pct) as avg_retorno,
                       AVG(overall_score) as avg_overall
                FROM trades
                WHERE resultado IS NOT NULL AND setup_key IS NOT NULL AND setup_key != ''
                GROUP BY setup_key
                HAVING total >= ?
                ORDER BY wins DESC
            """, (min_trades,)).fetchall()

        result = []
        for r in rows:
            total = r["total"]
            wins = r["wins"]
            losses = r["losses"]
            wr = wins / total * 100 if total > 0 else 0.0
            pf = wins / losses if losses > 0 else float("inf")
            result.append({
                "setup": r["setup_key"],
                "total": total,
                "wins": wins,
                "losses": losses,
                "breakeven": r["be"],
                "win_rate": round(wr, 2),
                "profit_factor": round(pf, 2) if pf != float("inf") else None,
                "avg_retorno_pct": round(r["avg_retorno"] or 0, 2),
                "avg_overall": round(r["avg_overall"] or 0, 1),
            })

        result.sort(key=lambda x: (x["win_rate"], x["profit_factor"] or 0), reverse=True)
        return result

    # --- LOSS ANALYSIS -----------------------------------------------------

    def get_loss_analysis(self) -> Dict:
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT id, asset, quality, confidence, consensus, overall_score,
                       risk_reward, trend, classification, entry_price, stop_loss,
                       take_profit_1, retorno_pct, lucro_usdt
                FROM trades
                WHERE resultado='LOSS'
                ORDER BY closed_at DESC
            """).fetchall()

        analysis = []
        gate_counts = defaultdict(int)
        total_losses = len(rows)

        for r in rows:
            d = dict(r)
            gates = {}
            gates["quality"] = d.get("quality", 0) or 0
            gates["confidence"] = d.get("confidence", 0) or 0
            gates["consensus"] = d.get("consensus", 0) or 0
            gates["overall_score"] = d.get("overall_score", 0) or 0
            gates["risk_reward"] = d.get("risk_reward", 0) or 0

            weakest = min(gates, key=gates.get)
            weakest_val = gates[weakest]

            reasons = []
            q = gates["quality"]
            c = gates["confidence"]
            cn = gates["consensus"]
            os_val = gates["overall_score"]
            rr_val = gates["risk_reward"]

            thresholds = {
                "quality": 0.70,
                "confidence": 0.75,
                "consensus": 0.70,
                "overall_score": 75.0,
                "risk_reward": 2.0,
            }

            gate_labels = {
                "quality": "Quality baixo",
                "confidence": "Confian\u00e7a baixa",
                "consensus": "Consenso baixo",
                "overall_score": "Overall Score baixo",
                "risk_reward": "RR baixo",
            }

            main_reason = gate_labels.get(weakest, "Desconhecido")
            gate_counts[main_reason] += 1

            if q < 0.70:
                reasons.append("Quality baixo")
            if c < 0.75:
                reasons.append("Confian\u00e7a baixa")
            if cn < 0.70:
                reasons.append("Consenso baixo")
            if os_val < 75:
                reasons.append("Overall Score baixo")
            if rr_val < 2.0:
                reasons.append("RR baixo")

            if not reasons:
                reasons.append("Condi\u00e7\u00e3o adversa de mercado")

            analysis.append({
                "asset": d.get("asset", "?"),
                "overall_score": os_val,
                "weakest_gate": weakest,
                "weakest_value": weakest_val,
                "main_reason": main_reason,
                "reasons": reasons,
                "gates": {k: round(v, 4) if isinstance(v, float) else v for k, v in gates.items()},
                "retorno_pct": d.get("retorno_pct", 0),
                "lucro_usdt": d.get("lucro_usdt", 0),
            })

        ranking = sorted(gate_counts.items(), key=lambda x: -x[1])

        return {
            "total_losses": total_losses,
            "analysis": analysis[:20],
            "weak_gate_ranking": [(g, c, round(c / total_losses * 100, 1) if total_losses > 0 else 0) for g, c in ranking],
        }

    # --- WEEKLY REPORT -----------------------------------------------------

    def get_weekly_report(self) -> Dict:
        trades = self.get_closed_trades(days=7)
        if not trades:
            return {"status": "no_trades", "total": 0}

        stats = self.get_statistics()
        by_tf = self.get_statistics_by_timeframe()
        by_cls = self.get_statistics_by_classification()
        by_dir = self.get_statistics_by_direction()
        setups = self.get_setup_ranking(min_trades=1)
        loss_analysis = self.get_loss_analysis()

        asset_perf = defaultdict(lambda: {"total": 0, "wins": 0, "losses": 0, "pnl": 0.0})
        for t in trades:
            a = t.get("asset", "?")
            asset_perf[a]["total"] += 1
            if t.get("resultado") == "WIN":
                asset_perf[a]["wins"] += 1
                asset_perf[a]["pnl"] += (t.get("lucro_usdt", 0) or 0)
            elif t.get("resultado") == "LOSS":
                asset_perf[a]["losses"] += 1
                asset_perf[a]["pnl"] -= (t.get("perda_usdt", 0) or 0)

        best_asset = max(asset_perf.items(), key=lambda x: x[1]["pnl"]) if asset_perf else ("N/A", {})
        worst_asset = min(asset_perf.items(), key=lambda x: x[1]["pnl"]) if asset_perf else ("N/A", {})

        tf_perf = defaultdict(lambda: {"total": 0, "wins": 0, "losses": 0, "pnl": 0.0})
        for t in trades:
            tf = t.get("timeframe", "?")
            tf_perf[tf]["total"] += 1
            if t.get("resultado") == "WIN":
                tf_perf[tf]["wins"] += 1
                tf_perf[tf]["pnl"] += (t.get("lucro_usdt", 0) or 0)
            elif t.get("resultado") == "LOSS":
                tf_perf[tf]["losses"] += 1
                tf_perf[tf]["pnl"] -= (t.get("perda_usdt", 0) or 0)

        best_tf = max(tf_perf.items(), key=lambda x: x[1]["pnl"]) if tf_perf else ("N/A", {})
        worst_tf = min(tf_perf.items(), key=lambda x: x[1]["pnl"]) if tf_perf else ("N/A", {})

        cls_perf = defaultdict(lambda: {"total": 0, "wins": 0, "pnl": 0.0})
        for t in trades:
            c = t.get("classification", "N/A") or "N/A"
            cls_perf[c]["total"] += 1
            if t.get("resultado") == "WIN":
                cls_perf[c]["wins"] += 1
                cls_perf[c]["pnl"] += (t.get("lucro_usdt", 0) or 0)
            elif t.get("resultado") == "LOSS":
                cls_perf[c]["pnl"] -= (t.get("perda_usdt", 0) or 0)

        best_cls = max(cls_perf.items(), key=lambda x: x[1]["pnl"]) if cls_perf else ("N/A", {})
        worst_cls = min(cls_perf.items(), key=lambda x: x[1]["pnl"]) if cls_perf else ("N/A", {})

        report = {
            "period": "7 dias",
            "total": stats.get("total_trades", 0),
            "win_rate": stats.get("win_rate"),
            "profit_factor": stats.get("profit_factor"),
            "drawdown": stats.get("drawdown"),
            "retorno_total": round(stats.get("net_pnl", 0), 2),
            "expectancy": stats.get("expectancy"),
            "best_asset": best_asset[0],
            "best_asset_pnl": round(best_asset[1].get("pnl", 0), 2),
            "worst_asset": worst_asset[0],
            "worst_asset_pnl": round(worst_asset[1].get("pnl", 0), 2),
            "best_timeframe": best_tf[0],
            "best_timeframe_pnl": round(best_tf[1].get("pnl", 0), 2),
            "worst_timeframe": worst_tf[0],
            "worst_timeframe_pnl": round(worst_tf[1].get("pnl", 0), 2),
            "best_classification": best_cls[0],
            "worst_classification": worst_cls[0],
            "by_timeframe": by_tf,
            "by_classification": by_cls,
            "by_direction": by_dir,
            "setup_ranking": setups[:10],
            "loss_analysis": loss_analysis,
        }
        return report
