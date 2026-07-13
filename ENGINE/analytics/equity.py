"""RFC V20.0 Fase 6 — Curva da Banca (Equity Curve).

Reaproveita statistics.compute_profit_by_period (agregacao por periodo,
ja implementada na Fase 2) e TradeRegistry.get_statistics()["drawdown"]
(ja calculado) — adiciona apenas a curva ACUMULADA (equity ao longo do
tempo) e a rentabilidade percentual sobre o capital inicial.
"""
import json
import os
from typing import Dict, List

from ENGINE.common.trade_registry import TradeRegistry
from ENGINE.analytics import statistics as stats

ANALYTICS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "MEMORY", "analytics",
)
EQUITY_JSON_PATH = os.path.join(ANALYTICS_DIR, "equity.json")


def _cumulative_curve(period_profits: Dict[str, float]) -> List[Dict]:
    curve = []
    running = 0.0
    for period in sorted(period_profits.keys()):
        running += period_profits[period]
        curve.append({
            "periodo": period,
            "lucro_periodo": period_profits[period],
            "equity_acumulado": round(running, 2),
        })
    return curve


def build_equity_curve(registry: TradeRegistry, capital_inicial: float) -> Dict:
    trades = registry.get_closed_trades()
    base_stats = registry.get_statistics()
    net_pnl = base_stats.get("net_pnl", 0.0) if base_stats.get("status") != "no_trades" else 0.0

    capital_atual = round(capital_inicial + net_pnl, 2)
    rentabilidade_pct = round(net_pnl / capital_inicial * 100, 2) if capital_inicial > 0 else 0.0

    return {
        "capital_inicial": capital_inicial,
        "capital_atual": capital_atual,
        "rentabilidade_pct": rentabilidade_pct,
        "drawdown": base_stats.get("drawdown", 0.0),
        "curva_diaria": _cumulative_curve(stats.compute_profit_by_period(trades, "day")),
        "curva_semanal": _cumulative_curve(stats.compute_profit_by_period(trades, "week")),
        "curva_mensal": _cumulative_curve(stats.compute_profit_by_period(trades, "month")),
    }


def persist_equity_curve(registry: TradeRegistry, capital_inicial: float,
                          path: str = EQUITY_JSON_PATH) -> Dict:
    data = build_equity_curve(registry, capital_inicial)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return data
