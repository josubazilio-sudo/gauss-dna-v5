"""RFC V20.0 Fase 1 — Banco de Operacoes (camada de exportacao).

NAO registra trades — isso ja e feito por TradeRegistry.open_trade()/
close_trade() (chamados em main.py). Este modulo apenas EXPORTA um
snapshot consolidado, no schema pedido pela RFC, para consumo por
dashboard/app/API. Somente-leitura sobre TradeRegistry.
"""
import json
import os
from datetime import datetime
from typing import Dict, List, Optional

from ENGINE.common.trade_registry import TradeRegistry

ANALYTICS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "MEMORY", "analytics",
)
TRADES_JSON_PATH = os.path.join(ANALYTICS_DIR, "trades.json")


def _split_iso(ts: Optional[str]) -> (str, str):
    if not ts:
        return "", ""
    try:
        dt = datetime.fromisoformat(ts)
        return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M:%S")
    except (ValueError, TypeError):
        return ts, ""


def _duration_hours(opened_at: Optional[str], closed_at: Optional[str]) -> Optional[float]:
    if not opened_at or not closed_at:
        return None
    try:
        start = datetime.fromisoformat(opened_at)
        end = datetime.fromisoformat(closed_at)
        return round((end - start).total_seconds() / 3600.0, 2)
    except (ValueError, TypeError):
        return None


def _to_schema(row: Dict) -> Dict:
    """Mapeia uma linha de TradeRegistry para o schema pedido na RFC V20.0."""
    data, hora = _split_iso(row.get("opened_at"))
    resultado = row.get("resultado")
    status = "CLOSED" if resultado else "OPEN"
    return {
        "id": row.get("id"),
        "data": data,
        "hora": hora,
        "ativo": row.get("asset"),
        "direcao": row.get("direction"),
        "timeframe": row.get("timeframe"),
        "entrada": row.get("entry_price"),
        "stop": row.get("stop_loss"),
        "tp1": row.get("take_profit_1"),
        "tp2": row.get("take_profit_2"),
        "score": row.get("overall_score"),
        "confidence": row.get("confidence"),
        "quality": row.get("quality"),
        "setup": row.get("setup_key"),
        "status": status,
        "resultado": resultado,
        "lucro": row.get("lucro_usdt"),
        "prejuizo": row.get("perda_usdt"),
        "duracao_horas": _duration_hours(row.get("opened_at"), row.get("closed_at")),
    }


def collect_trades(registry: TradeRegistry, days: Optional[int] = None) -> List[Dict]:
    """Junta trades abertos + fechados (leitura apenas) no schema da RFC."""
    open_trades = [_to_schema(r) for r in registry.get_open_trades()]
    closed_trades = [_to_schema(r) for r in registry.get_closed_trades(days=days)]
    return open_trades + closed_trades


def export_trades_json(registry: TradeRegistry, days: Optional[int] = None,
                        path: str = TRADES_JSON_PATH) -> List[Dict]:
    """Exporta o snapshot consolidado para MEMORY/analytics/trades.json.
    Retorna a lista exportada (para uso direto por outros modulos, sem
    precisar reler o arquivo)."""
    trades = collect_trades(registry, days=days)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(trades, f, indent=2, ensure_ascii=False)
    return trades
