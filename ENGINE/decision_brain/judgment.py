import logging
from typing import Dict, List, Optional, Tuple

from ENGINE.scanner.scanner_types import Signal, ScannerScore
from .decision_brain_types import (
    OperationalThesis, CounterThesis, Judgment, DecisionState, PESOS_PADRAO,
)

log = logging.getLogger(__name__)


def calcular_probabilidade(tese_score: float, contra_score: float, pesos: Optional[Dict[str, float]] = None) -> float:
    p = pesos or PESOS_PADRAO
    raw = tese_score * p["tese_score"] + (1.0 - contra_score) * p["contra_tese_score"]
    return max(0.05, min(0.95, raw))


def calcular_conviccao(tese_score: float, contra_score: float, signal: Signal) -> float:
    conv_raw = signal.scores.conviction_score if signal.scores else 0.0
    ajuste = (tese_score - contra_score) * 0.3
    return max(0.0, min(1.0, conv_raw + ajuste))


def calcular_risco(contra_score: float, signal: Signal) -> float:
    base_risk = signal.scores.risk_score if signal.scores else 0.5
    risco_contra = contra_score * 0.4
    return max(0.05, min(0.95, base_risk * 0.6 + risco_contra))


def calcular_expectancy(prob: float, risco: float, rr: float) -> float:
    if risco <= 0:
        return 0.0
    return (prob * rr * 0.5) - ((1.0 - prob) * 0.5)


def determinar_estado(
    probabilidade: float,
    conviccao: float,
    risco: float,
    tese_score: float,
    contra_score: float,
    signal: Signal,
) -> DecisionState:
    if probabilidade < 0.35 or conviccao < 0.30:
        return DecisionState.REJEITADO

    if signal.stop_loss <= 0 or signal.risk_reward <= 0:
        return DecisionState.REJEITADO

    if risco > 0.65:
        return DecisionState.OBSERVACAO

    if probabilidade < 0.55 or conviccao < 0.45 or (tese_score - contra_score) < 0.10:
        return DecisionState.OBSERVACAO

    if probabilidade >= 0.70 and conviccao >= 0.60 and risco <= 0.35 and contra_score < 0.40:
        return DecisionState.EXECUTAR

    return DecisionState.PRONTO


def _build_justificativa(
    tese_score: float,
    contra_score: float,
    probabilidade: float,
    conviccao: float,
    risco: float,
    expectancy: float,
    estado: DecisionState,
    tese: OperationalThesis,
    contra_tese: CounterThesis,
) -> str:
    partes = []
    partes.append(f"Tese: {tese_score:.2f} | Contra-Tese: {contra_score:.2f}")
    partes.append(f"Probabilidade: {probabilidade:.2%}")
    partes.append(f"Conviccao: {conviccao:.2%}")
    partes.append(f"Risco: {risco:.2%}")
    partes.append(f"Expectancy: {expectancy:.4f}")
    partes.append(f"Decisao: {estado.value}")

    ativos_ct = [f for f in contra_tese.fatores if f.ativo]
    if ativos_ct:
        partes.append("Contra-teses ativas:")
        for f in ativos_ct:
            partes.append(f"  - {f.nome} (peso {f.peso:.2f}): {f.justificativa}")

    partes.append(f"Regime: {tese.regime}")
    partes.append(f"Contexto: {tese.contexto_macro}")
    return " | ".join(partes)


def make_judgment(
    tese: OperationalThesis,
    contra_tese: CounterThesis,
    signal: Signal,
    pesos_override: Optional[Dict[str, float]] = None,
) -> Judgment:
    pesos = dict(PESOS_PADRAO)
    if pesos_override:
        pesos.update(pesos_override)
    tese_score = tese.score_total
    contra_score = contra_tese.score_contra

    probabilidade = calcular_probabilidade(tese_score, contra_score, pesos)
    conviccao = calcular_conviccao(tese_score, contra_score, signal)
    risco = calcular_risco(contra_score, signal)
    expectancy = calcular_expectancy(probabilidade, risco, signal.risk_reward)
    estado = determinar_estado(probabilidade, conviccao, risco, tese_score, contra_score, signal)
    justificativa = _build_justificativa(
        tese_score, contra_score, probabilidade, conviccao, risco,
        expectancy, estado, tese, contra_tese,
    )

    return Judgment(
        probabilidade=round(probabilidade, 4),
        conviccao=round(conviccao, 4),
        risco=round(risco, 4),
        expectancy=round(expectancy, 4),
        recomendacao=estado,
        justificativa=justificativa,
        tese=tese,
        contra_tese=contra_tese,
    )
