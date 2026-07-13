"""RFC V20.0 Fase 5 — Diario Automatico.

Para cada trade fechado em TradeRegistry, gera uma entrada de diario
(entrada/stop/TP/resultado/lucro/tempo/observacoes auto-geradas) e
acrescenta (append-only, JSON Lines) a MEMORY/analytics/journal.jsonl.
Sem intervencao manual — le do TradeRegistry, nunca escreve nele.
Idempotente: chamado uma vez por ciclo, so adiciona trades ainda nao
registrados no diario.
"""
import json
import os
from typing import Dict, List, Optional, Set

from ENGINE.common.trade_registry import TradeRegistry
from ENGINE.analytics.trade_storage import _duration_hours

ANALYTICS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "MEMORY", "analytics",
)
JOURNAL_PATH = os.path.join(ANALYTICS_DIR, "journal.jsonl")


def _observacoes(trade: Dict) -> str:
    parts = []
    if trade.get("setup_key"):
        parts.append(f"Setup: {trade['setup_key']}")
    if trade.get("classification"):
        parts.append(f"Classificacao: {trade['classification']}")
    if trade.get("risk_reward"):
        parts.append(f"RR planejado: {trade['risk_reward']}")
    resultado = trade.get("resultado")
    if resultado == "WIN":
        parts.append("Operacao encerrada em lucro.")
    elif resultado == "LOSS":
        parts.append("Operacao encerrada em prejuizo.")
    elif resultado == "BREAKEVEN":
        parts.append("Operacao encerrada no zero a zero.")
    return " | ".join(parts)


def build_entry(trade: Dict) -> Dict:
    lucro_liquido = (trade.get("lucro_usdt", 0) or 0) - (trade.get("perda_usdt", 0) or 0)
    return {
        "id": trade.get("id"),
        "ativo": trade.get("asset"),
        "direcao": trade.get("direction"),
        "entrada": trade.get("entry_price"),
        "stop": trade.get("stop_loss"),
        "tp": trade.get("take_profit_1"),
        "resultado": trade.get("resultado"),
        "lucro": round(lucro_liquido, 2),
        "tempo_horas": _duration_hours(trade.get("opened_at"), trade.get("closed_at")),
        "observacoes": _observacoes(trade),
        "data_fechamento": trade.get("closed_at"),
    }


def _load_existing_ids(path: str) -> Set[str]:
    ids: Set[str] = set()
    if not os.path.exists(path):
        return ids
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ids.add(json.loads(line).get("id"))
            except json.JSONDecodeError:
                continue
    return ids


def append_new_entries(registry: TradeRegistry, path: str = JOURNAL_PATH) -> List[Dict]:
    """Idempotente: so adiciona trades fechados que ainda nao estao no
    diario. Retorna as entradas novas adicionadas nesta chamada."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    existing_ids = _load_existing_ids(path)
    closed = registry.get_closed_trades()
    new_entries = [build_entry(t) for t in closed if t.get("id") not in existing_ids]
    if new_entries:
        with open(path, "a", encoding="utf-8") as f:
            for entry in new_entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return new_entries
