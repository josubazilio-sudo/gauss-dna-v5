"""RFC V20.0 Fase 2 — Engine de Estatisticas.

Consolida TradeRegistry.get_statistics() (ja calcula win_rate,
profit_factor, drawdown, payoff, expectancy, avg_rr — nao recalculado
aqui) e adiciona apenas o que ainda nao existe: lucro diario/semanal/
mensal, maiores sequencias win/loss, duracao media das operacoes, taxa
de acerto por ativo. Persiste em MEMORY/analytics/metrics.json.
"""
import json
import os
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional

from ENGINE.common.trade_registry import TradeRegistry

ANALYTICS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "MEMORY", "analytics",
)
METRICS_JSON_PATH = os.path.join(ANALYTICS_DIR, "metrics.json")


def _period_key(iso_ts: str, granularity: str) -> Optional[str]:
    try:
        dt = datetime.fromisoformat(iso_ts)
    except (ValueError, TypeError):
        return None
    if granularity == "day":
        return dt.strftime("%Y-%m-%d")
    if granularity == "week":
        iso = dt.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}"
    if granularity == "month":
        return dt.strftime("%Y-%m")
    raise ValueError(f"granularidade invalida: {granularity}")


def compute_profit_by_period(trades: List[Dict], granularity: str) -> Dict[str, float]:
    buckets: Dict[str, float] = defaultdict(float)
    for t in trades:
        closed_at = t.get("closed_at")
        if not closed_at:
            continue
        key = _period_key(closed_at, granularity)
        if key is None:
            continue
        pnl = (t.get("lucro_usdt", 0) or 0) - (t.get("perda_usdt", 0) or 0)
        buckets[key] += pnl
    return {k: round(v, 2) for k, v in sorted(buckets.items())}


def compute_streaks(trades: List[Dict]) -> Dict[str, int]:
    ordered = sorted(
        [t for t in trades if t.get("resultado") in ("WIN", "LOSS")],
        key=lambda t: t.get("closed_at") or "",
    )
    max_win_streak = max_loss_streak = cur_win = cur_loss = 0
    for t in ordered:
        if t["resultado"] == "WIN":
            cur_win += 1
            cur_loss = 0
        else:
            cur_loss += 1
            cur_win = 0
        max_win_streak = max(max_win_streak, cur_win)
        max_loss_streak = max(max_loss_streak, cur_loss)
    return {"max_win_streak": max_win_streak, "max_loss_streak": max_loss_streak}


def compute_avg_duration_hours(trades: List[Dict]) -> Optional[float]:
    durations = []
    for t in trades:
        opened, closed = t.get("opened_at"), t.get("closed_at")
        if not opened or not closed:
            continue
        try:
            start = datetime.fromisoformat(opened)
            end = datetime.fromisoformat(closed)
            durations.append((end - start).total_seconds() / 3600.0)
        except (ValueError, TypeError):
            continue
    return round(sum(durations) / len(durations), 2) if durations else None


def compute_win_rate_by_asset(trades: List[Dict]) -> Dict[str, Dict]:
    by_asset: Dict[str, Dict] = defaultdict(lambda: {"total": 0, "wins": 0, "losses": 0})
    for t in trades:
        if t.get("resultado") not in ("WIN", "LOSS"):
            continue
        asset = t.get("asset", "?")
        by_asset[asset]["total"] += 1
        if t["resultado"] == "WIN":
            by_asset[asset]["wins"] += 1
        else:
            by_asset[asset]["losses"] += 1
    result = {}
    for asset, d in by_asset.items():
        wr = d["wins"] / d["total"] * 100 if d["total"] else 0.0
        result[asset] = {**d, "win_rate": round(wr, 2)}
    return result


def compute_metrics(registry: TradeRegistry) -> Dict:
    """Ponto de entrada unico: consolida o que TradeRegistry ja calcula
    corretamente + adiciona o que falta. Nenhum Win Rate/Profit Factor/
    Drawdown/Expectancy e recalculado aqui — vem de registry.get_statistics()."""
    base = registry.get_statistics()
    empty_extras = {
        "lucro_diario": {}, "lucro_semanal": {}, "lucro_mensal": {},
        "max_win_streak": 0, "max_loss_streak": 0,
        "duracao_media_horas": None,
        "win_rate_por_ativo": {}, "win_rate_por_timeframe": {},
    }
    if base.get("status") == "no_trades":
        return {**base, **empty_extras}

    trades = registry.get_closed_trades()
    return {
        **base,
        "lucro_diario": compute_profit_by_period(trades, "day"),
        "lucro_semanal": compute_profit_by_period(trades, "week"),
        "lucro_mensal": compute_profit_by_period(trades, "month"),
        **compute_streaks(trades),
        "duracao_media_horas": compute_avg_duration_hours(trades),
        "win_rate_por_ativo": compute_win_rate_by_asset(trades),
        "win_rate_por_timeframe": registry.get_statistics_by_timeframe(),
    }


def persist_metrics(registry: TradeRegistry, path: str = METRICS_JSON_PATH) -> Dict:
    metrics = compute_metrics(registry)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)
    return metrics
