"""RFC V20.0 Fase 4 — Gestao de Risco (calculadora auxiliar).

Recebe banca + risco% + entrada + stop [+ take_profit opcional] e devolve
quantidade, valor da posicao, perda maxima, lucro esperado, RR e
alavancagem sugerida. NUNCA altera o sinal original — e apenas uma
calculadora pura. Reaproveita OperationalCalculator (ja existente e
testado) para o calculo monetario, evitando duplicar formula de lucro/
perda.
"""
from typing import Dict, Optional

from ENGINE.common.operational import OperationalCalculator

# Alavancagem sugerida: heuristica simples e conservadora — quanto maior o
# risco% por trade, menor a alavancagem sugerida. Nao e regra institucional
# do Decision Engine, e apenas uma sugestao desta calculadora auxiliar.
_LEVERAGE_SUGGESTION_TABLE = [
    (0.01, 10),
    (0.02, 7),
    (0.03, 5),
    (0.05, 3),
]
_LEVERAGE_DEFAULT = 1


def suggest_leverage(risco_pct: float) -> int:
    for threshold, leverage in _LEVERAGE_SUGGESTION_TABLE:
        if risco_pct <= threshold:
            return leverage
    return _LEVERAGE_DEFAULT


def _empty_result(leverage: int = _LEVERAGE_DEFAULT) -> Dict:
    return {
        "quantidade": 0.0, "valor_posicao": 0.0, "perda_maxima": 0.0,
        "lucro_esperado": 0.0, "rr": 0.0, "alavancagem_sugerida": leverage,
    }


def calculate_position(
    banca: float,
    risco_pct: float,
    entrada: float,
    stop: float,
    take_profit: Optional[float] = None,
    calculator: Optional[OperationalCalculator] = None,
) -> Dict:
    """Calculadora pura de gestao de risco. Nao executa ordem nenhuma."""
    if banca <= 0 or entrada <= 0 or risco_pct <= 0:
        return _empty_result()

    price_risk = abs(entrada - stop)
    if price_risk <= 0:
        return _empty_result()

    valor_arriscado = banca * risco_pct
    quantidade = valor_arriscado / price_risk
    leverage = suggest_leverage(risco_pct)

    calc = calculator or OperationalCalculator()
    ops = calc.calculate(
        entry_price=entrada, stop_loss=stop,
        take_profit_1=take_profit or 0.0,
        quantity=quantidade, balance=banca, leverage=leverage,
    )

    rr = round(abs(take_profit - entrada) / price_risk, 2) if take_profit else 0.0

    return {
        "quantidade": round(quantidade, 6),
        "valor_posicao": ops.get("valor_nominal", 0.0),
        "perda_maxima": ops.get("perda_maxima_usdt") or round(valor_arriscado, 2),
        "lucro_esperado": ops.get("lucro_liquido_usdt", 0.0),
        "rr": rr,
        "alavancagem_sugerida": leverage,
    }
