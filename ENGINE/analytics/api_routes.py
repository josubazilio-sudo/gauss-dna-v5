"""RFC V20.0 Fase 9 — Preparacao para API REST futura.

Funcoes puras que retornam dicts serializaveis em JSON, mapeando 1:1
para as rotas /dashboard, /trades, /metrics, /risk, /equity pedidas na
RFC — prontas para serem penduradas em um framework HTTP (Flask/FastAPI)
quando houver integracao real com app Android/painel Web.

IMPORTANTE: este modulo NAO abre nenhuma porta nem inicia servidor HTTP.
Isso mudaria a superficie de rede da VPS em producao e e uma decisao
separada, fora do escopo desta RFC (ver RFC_V20_0_ANALYTICS_PLATFORM.md).
"""
from typing import Dict, List, Optional

from ENGINE.common.trade_registry import TradeRegistry
from ENGINE.analytics import trade_storage
from ENGINE.analytics import statistics as stats
from ENGINE.analytics import dashboard as dash
from ENGINE.analytics import equity as eq
from ENGINE.analytics import risk_manager as rm


def get_dashboard(registry: TradeRegistry, **kwargs) -> Dict:
    """Equivalente a GET /dashboard."""
    return dash.build_dashboard(registry, **kwargs)


def get_trades(registry: TradeRegistry, days: Optional[int] = None) -> List[Dict]:
    """Equivalente a GET /trades."""
    return trade_storage.collect_trades(registry, days=days)


def get_metrics(registry: TradeRegistry) -> Dict:
    """Equivalente a GET /metrics."""
    return stats.compute_metrics(registry)


def get_risk(banca: float, risco_pct: float, entrada: float, stop: float,
             take_profit: Optional[float] = None) -> Dict:
    """Equivalente a POST /risk. Calculadora pura — nunca executa ordem."""
    return rm.calculate_position(banca, risco_pct, entrada, stop, take_profit)


def get_equity(registry: TradeRegistry, capital_inicial: float) -> Dict:
    """Equivalente a GET /equity."""
    return eq.build_equity_curve(registry, capital_inicial)


# Mapa rota -> funcao, para quando um framework HTTP real for conectado.
ROUTES = {
    "GET /dashboard": get_dashboard,
    "GET /trades": get_trades,
    "GET /metrics": get_metrics,
    "POST /risk": get_risk,
    "GET /equity": get_equity,
}
