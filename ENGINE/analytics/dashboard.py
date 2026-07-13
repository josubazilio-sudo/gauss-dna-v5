"""RFC V20.0 Fase 3 — Dashboard.

Funcao pura que consolida dados JA calculados por statistics.py,
TradeRegistry.get_weekly_report() e (opcionalmente) pelo ciclo em
andamento (health do scanner, saude de mercado, saldo, insights de
performance) — nao recalcula nenhuma metrica, so monta o dict de exibicao.
"""
from datetime import datetime, timezone
from typing import Dict, Optional

from ENGINE.common.trade_registry import TradeRegistry
from ENGINE.analytics import statistics as stats


def _trades_today(registry: TradeRegistry) -> list:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    closed = registry.get_closed_trades(days=2)  # margem de fuso horario
    return [t for t in closed if (t.get("closed_at") or "").startswith(today)]


def build_dashboard(
    registry: TradeRegistry,
    scanner_health: Optional[Dict] = None,
    market_health: Optional[Dict] = None,
    banca: Optional[float] = None,
    insights: Optional[Dict] = None,
) -> Dict:
    """Monta o dashboard em tempo real. Todos os parametros opcionais sao
    fornecidos pelo chamador (main.py) a partir de dados JA calculados no
    ciclo — este modulo nunca busca dados por conta propria."""
    metrics = stats.compute_metrics(registry)
    today_trades = _trades_today(registry)
    wins_today = sum(1 for t in today_trades if t.get("resultado") == "WIN")
    losses_today = sum(1 for t in today_trades if t.get("resultado") == "LOSS")
    lucro_hoje = sum(
        (t.get("lucro_usdt", 0) or 0) - (t.get("perda_usdt", 0) or 0)
        for t in today_trades
    )

    weekly = registry.get_weekly_report()
    best_asset = weekly.get("best_asset") if weekly.get("status") != "no_trades" else None
    worst_asset = weekly.get("worst_asset") if weekly.get("status") != "no_trades" else None
    best_timeframe = weekly.get("best_timeframe") if weekly.get("status") != "no_trades" else None

    return {
        "scanner_status": (scanner_health or {}).get("loop_status", "DESCONHECIDO"),
        "mercado": (market_health or {}).get("classificacao", "N/A"),
        "operacoes_hoje": len(today_trades),
        "wins_hoje": wins_today,
        "losses_hoje": losses_today,
        "lucro_hoje": round(lucro_hoje, 2),
        "win_rate": metrics.get("win_rate"),
        "profit_factor": metrics.get("profit_factor"),
        "drawdown": metrics.get("drawdown"),
        "lucro_total": metrics.get("net_pnl"),
        "banca": banca,
        "melhor_ativo": best_asset,
        "pior_ativo": worst_asset,
        "melhor_horario": (insights or {}).get("melhor_horario"),
        "melhor_timeframe": best_timeframe,
        "proximo_ciclo_em_s": (scanner_health or {}).get("next_cycle_in_s"),
        "last_update": datetime.now(timezone.utc).isoformat(),
    }
