"""RFC V20.0 Fase 7 — Performance Insights.

Reaproveita TradeRegistry.get_setup_ranking() (ja calcula melhor setup,
historico completo, sem filtro de dias) — adiciona apenas o que ainda nao
existe: melhor/pior ativo, timeframe, horario e dia da semana (calculados
sobre o HISTORICO COMPLETO, nao apenas os ultimos 7 dias de
get_weekly_report()), alem de maior lucro/perda individuais.
"""
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from ENGINE.common.trade_registry import TradeRegistry

_WEEKDAY_PT = ["Segunda", "Terca", "Quarta", "Quinta", "Sexta", "Sabado", "Domingo"]


def _trade_pnl(t: Dict) -> float:
    return (t.get("lucro_usdt", 0) or 0) - (t.get("perda_usdt", 0) or 0)


def _pnl_by_key(trades: List[Dict], key_fn) -> Dict[str, float]:
    by_key: Dict[str, float] = defaultdict(float)
    for t in trades:
        key = key_fn(t)
        if key is None:
            continue
        by_key[key] += _trade_pnl(t)
    return dict(by_key)


def _best_worst(d: Dict[str, float]) -> Tuple[Optional[str], Optional[str]]:
    if not d:
        return None, None
    best = max(d.items(), key=lambda kv: kv[1])[0]
    worst = min(d.items(), key=lambda kv: kv[1])[0]
    return best, worst


def compute_performance_by_hour(trades: List[Dict]) -> Dict[str, float]:
    def hour_key(t):
        closed_at = t.get("closed_at")
        if not closed_at:
            return None
        try:
            return f"{datetime.fromisoformat(closed_at).hour}h"
        except (ValueError, TypeError):
            return None
    return _pnl_by_key(trades, hour_key)


def compute_performance_by_weekday(trades: List[Dict]) -> Dict[str, float]:
    def weekday_key(t):
        closed_at = t.get("closed_at")
        if not closed_at:
            return None
        try:
            return _WEEKDAY_PT[datetime.fromisoformat(closed_at).weekday()]
        except (ValueError, TypeError):
            return None
    return _pnl_by_key(trades, weekday_key)


def compute_insights(registry: TradeRegistry) -> Dict:
    """Historico completo (sem filtro de dias) — Fase 7 exige que 'todos
    os dados sejam calculados a partir do historico real', nao apenas os
    ultimos 7 dias usados por TradeRegistry.get_weekly_report()."""
    trades = registry.get_closed_trades()
    if not trades:
        return {
            "melhor_ativo": None, "pior_ativo": None,
            "melhor_horario": None, "pior_horario": None,
            "melhor_dia": None, "pior_dia": None,
            "melhor_setup": None, "melhor_timeframe": None,
            "maior_lucro": 0.0, "maior_perda": 0.0,
        }

    by_asset = _pnl_by_key(trades, lambda t: t.get("asset"))
    by_timeframe = _pnl_by_key(trades, lambda t: t.get("timeframe"))
    by_hour = compute_performance_by_hour(trades)
    by_weekday = compute_performance_by_weekday(trades)

    best_asset, worst_asset = _best_worst(by_asset)
    best_tf, _ = _best_worst(by_timeframe)
    best_hour, worst_hour = _best_worst(by_hour)
    best_day, worst_day = _best_worst(by_weekday)

    setups = registry.get_setup_ranking(min_trades=1)
    melhor_setup = setups[0]["setup"] if setups else None

    pnls = [_trade_pnl(t) for t in trades]

    return {
        "melhor_ativo": best_asset,
        "pior_ativo": worst_asset,
        "melhor_horario": best_hour,
        "pior_horario": worst_hour,
        "melhor_dia": best_day,
        "pior_dia": worst_day,
        "melhor_setup": melhor_setup,
        "melhor_timeframe": best_tf,
        "maior_lucro": round(max(pnls), 2),
        "maior_perda": round(min(pnls), 2),
    }
