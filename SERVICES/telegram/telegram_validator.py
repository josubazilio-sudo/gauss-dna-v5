"""
Validador de Sinais e Decisões para o Telegram.
Responsável APENAS por validar campos obrigatórios antes da formatação/envio.
"""
import logging
from typing import Tuple, Dict, Any

from ENGINE.common.operational import _derive_tier

log = logging.getLogger(__name__)

def validate_signal_data(data: Dict[str, Any]) -> Tuple[bool, str]:
    """Valida se os campos obrigatórios para o envio estão presentes."""
    required = ["pair", "direction", "entry_price"]
    for field in required:
        if field not in data or data[field] is None:
            return False, f"Campo obrigatório faltando: {field}"
    
    # Validações de valores
    if data["entry_price"] <= 0:
        return False, f"Preço de entrada inválido: {data['entry_price']}"
        
    return True, "OK"

def validate_consistency(data: Dict[str, Any]) -> bool:
    """Verifica se os campos de aprovacao dos hard gates do DecisionEngine
    atual (8 gates, ver ENGINE/decision/decision_engine.py) estao presentes
    e corretos. Antes esta lista incluia 18 campos de um DecisionEngine V10
    ja removido (institutional_ok, flow_ok, timing_ok, liquidity_ok,
    structural_ok, conviction_ok, market_ok, trend_ok, confidence_ok,
    risk_ok) que o motor atual nunca define (ficam None por padrao em
    SignalDecision) — isso bloqueava silenciosamente todo sinal aprovado."""
    ok_fields = [
        "rvol_ok", "adx_ok", "structure_ok", "entry_zone_ok",
        "entry_score_ok", "quality_ok", "consensus_ok", "rr_ok",
    ]

    for field in ok_fields:
        if not data.get(field, False):
            return False
    return True


def validate_presentation_consistency(data: Dict[str, Any]) -> Tuple[bool, str]:
    """RFC V20.2: valida que os DADOS que serao exibidos no card do
    Telegram sao internamente coerentes (nao valida gates de negocio —
    isso e validate_consistency). Se algo aqui falhar, o card mostraria
    uma contradicao visivel (ex.: precos fora de ordem, RR que nao bate
    com os precos reais, ou classificacao divergente do score numerico)
    — melhor cancelar o envio e logar do que mostrar dado quebrado."""
    direction = str(data.get("direction", "") or "").upper()
    entry = float(data.get("entry_price", 0) or 0)
    stop = float(data.get("stop_loss", 0) or 0)
    tp1 = float(data.get("take_profit_1", 0) or 0)

    if entry <= 0:
        return False, f"Preco de entrada invalido: {entry}"

    is_long = direction in ("LONG", "BUY")
    is_short = direction in ("SHORT", "SELL")

    if stop > 0 and tp1 > 0:
        if is_long and not (stop < entry < tp1):
            return False, (
                f"Precos fora de ordem para LONG: stop={stop} entry={entry} tp1={tp1}"
            )
        if is_short and not (tp1 < entry < stop):
            return False, (
                f"Precos fora de ordem para SHORT: stop={stop} entry={entry} tp1={tp1}"
            )

    risk_reward = float(data.get("risk_reward", 0) or 0)
    if risk_reward > 0 and stop > 0 and tp1 > 0:
        price_risk = abs(entry - stop)
        price_reward = abs(tp1 - entry)
        if price_risk > 0:
            computed_rr = price_reward / price_risk
            tolerance = max(0.3, risk_reward * 0.2)
            if abs(computed_rr - risk_reward) > tolerance:
                return False, (
                    f"RR exibido ({risk_reward:.2f}) nao bate com os precos "
                    f"(RR real={computed_rr:.2f})"
                )

    overall = data.get("overall_score")
    if isinstance(overall, dict):
        score_val = overall.get("overall_score")
        tier_val = overall.get("overall_tier")
        if score_val is not None and tier_val:
            _, expected_tier = _derive_tier(float(score_val))
            if expected_tier != tier_val:
                return False, (
                    f"Tier exibido ({tier_val}) nao bate com overall_score "
                    f"({score_val} -> esperado {expected_tier})"
                )

    return True, "OK"
