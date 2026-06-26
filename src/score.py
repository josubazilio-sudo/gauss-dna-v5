"""Módulo 8: Score Institucional e Classificação."""

from config import SCORE_WEIGHTS, CLASSIFICATION


def calculate_score(trend, flow, smc, momentum):
    """
    Calcula score institucional baseado nas confirmações de cada módulo.
    """
    score = 0
    trend_direction, trend_mas = trend

    if trend_direction in ("muito_forte", "forte"):
        score += SCORE_WEIGHTS["tendencia"]

    if flow.get("rvol", 0) > 1.2 and flow.get("volume_crescente"):
        score += SCORE_WEIGHTS["fluxo"]

    if smc.get("bos"):
        score += SCORE_WEIGHTS["estrutura"]
    if smc.get("order_block"):
        score += SCORE_WEIGHTS["liquidez"] * 0.5
    if smc.get("fvg"):
        score += SCORE_WEIGHTS["liquidez"] * 0.5

    if momentum.get("adx", 0) > 20:
        score += SCORE_WEIGHTS["momentum"]

    if flow.get("rvol", 0) > 1.0:
        vol_score = min(flow["rvol"] * 5, 10)
        score += vol_score

    if momentum.get("atr", 0) > 0:
        score += SCORE_WEIGHTS["volatilidade"]

    return min(score, 100)


def classify_signal(score):
    """
    Classifica sinal como OURO, PRATA ou BRONZE.
    """
    for grade, params in sorted(
        CLASSIFICATION.items(), key=lambda x: x[1]["min_score"], reverse=True
    ):
        if score >= params["min_score"]:
            return grade
    return None
