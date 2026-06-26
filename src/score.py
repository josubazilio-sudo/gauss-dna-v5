"""Score Institucional — preenche variáveis SCORE e CLASSIFICAÇÃO."""

from config import (
    PESO_TENDENCIA, PESO_FLUXO, PESO_VOLUME, PESO_LIQUIDEZ,
    PESO_ESTRUTURA, PESO_MOMENTUM, PESO_VOLATILIDADE,
    SCORE_OURO_MIN, SCORE_PRATA_MIN, SCORE_BRONZE_MIN,
)


def calculate_score(config, trend_data, flow_data, smc_data, momentum_data, market_data):
    """
    Preenche SCORE_TENDENCIA, SCORE_VOLUME, SCORE_FLUXO,
    SCORE_MOMENTUM, SCORE_LIQUIDEZ, SCORE_ESTRUTURA,
    SCORE_VOLATILIDADE, SCORE_TOTAL.
    """
    result = {
        "SCORE_TENDENCIA": 0,
        "SCORE_VOLUME": 0,
        "SCORE_FLUXO": 0,
        "SCORE_MOMENTUM": 0,
        "SCORE_LIQUIDEZ": 0,
        "SCORE_ESTRUTURA": 0,
        "SCORE_VOLATILIDADE": 0,
        "SCORE_TOTAL": 0,
    }

    # Tendência
    if trend_data.get("TENDENCIA") in ("alta", "alta_moderada", "baixa", "baixa_moderada"):
        result["SCORE_TENDENCIA"] = PESO_TENDENCIA
    if trend_data.get("EMA_ALINHADA"):
        result["SCORE_TENDENCIA"] = min(result["SCORE_TENDENCIA"] + 5, PESO_TENDENCIA)

    # Fluxo
    if flow_data.get("DELTA_POSITIVO") and trend_data.get("DIRECAO") == "long":
        result["SCORE_FLUXO"] = PESO_FLUXO
    elif flow_data.get("DELTA_NEGATIVO") and trend_data.get("DIRECAO") == "short":
        result["SCORE_FLUXO"] = PESO_FLUXO
    elif flow_data.get("DELTA") != 0:
        result["SCORE_FLUXO"] = PESO_FLUXO // 2

    # Volume
    if flow_data.get("RVOL", 0) >= flow_data.get("RVOL_MINIMO", 1.2):
        result["SCORE_VOLUME"] = PESO_VOLUME
    if flow_data.get("VOLUME_CRESCENTE"):
        result["SCORE_VOLUME"] = min(result["SCORE_VOLUME"] + 5, PESO_VOLUME)

    # Momentum
    if momentum_data.get("ADX", 0) >= config.get("ADX_MINIMO", 20):
        result["SCORE_MOMENTUM"] = PESO_MOMENTUM
    if momentum_data.get("MOMENTUM") == "crescente" and trend_data.get("DIRECAO") == "long":
        result["SCORE_MOMENTUM"] = min(result["SCORE_MOMENTUM"] + 5, PESO_MOMENTUM)
    elif momentum_data.get("MOMENTUM") == "decrescente" and trend_data.get("DIRECAO") == "short":
        result["SCORE_MOMENTUM"] = min(result["SCORE_MOMENTUM"] + 5, PESO_MOMENTUM)

    # Liquidez
    if smc_data.get("LIQUIDITY_SWEEP"):
        result["SCORE_LIQUIDEZ"] = PESO_LIQUIDEZ
    if smc_data.get("RETESTE"):
        result["SCORE_LIQUIDEZ"] = min(result["SCORE_LIQUIDEZ"] + 5, PESO_LIQUIDEZ)

    # Estrutura
    if smc_data.get("BOS"):
        result["SCORE_ESTRUTURA"] = PESO_ESTRUTURA
    if smc_data.get("ESTRUTURA_OK"):
        result["SCORE_ESTRUTURA"] = min(result["SCORE_ESTRUTURA"] + 5, PESO_ESTRUTURA)

    # Volatilidade
    if market_data.get("VOLATILIDADE") == "alta" or market_data.get("ATR_EXPANSAO"):
        result["SCORE_VOLATILIDADE"] = PESO_VOLATILIDADE

    result["SCORE_TOTAL"] = min(sum([
        result["SCORE_TENDENCIA"],
        result["SCORE_FLUXO"],
        result["SCORE_VOLUME"],
        result["SCORE_MOMENTUM"],
        result["SCORE_LIQUIDEZ"],
        result["SCORE_ESTRUTURA"],
        result["SCORE_VOLATILIDADE"],
    ]), 100)

    return result


def classify_signal(score_total, confianca=100):
    """
    Preenche SINAL_OURO, SINAL_PRATA, SINAL_BRONZE,
    NIVEL_CONFIANCA, QUALIDADE_SINAL, CLASSIFICACAO_FINAL.
    """
    result = {
        "SINAL_OURO": False,
        "SINAL_PRATA": False,
        "SINAL_BRONZE": False,
        "NIVEL_CONFIANCA": confianca,
        "QUALIDADE_SINAL": "",
        "CLASSIFICACAO_FINAL": "",
    }

    if score_total >= SCORE_OURO_MIN:
        result["SINAL_OURO"] = True
        result["CLASSIFICACAO_FINAL"] = "OURO"
        result["QUALIDADE_SINAL"] = "excelente"
    elif score_total >= SCORE_PRATA_MIN:
        result["SINAL_PRATA"] = True
        result["CLASSIFICACAO_FINAL"] = "PRATA"
        result["QUALIDADE_SINAL"] = "boa"
    elif score_total >= SCORE_BRONZE_MIN:
        result["SINAL_BRONZE"] = True
        result["CLASSIFICACAO_FINAL"] = "BRONZE"
        result["QUALIDADE_SINAL"] = "aceitavel"
    else:
        result["CLASSIFICACAO_FINAL"] = ""
        result["QUALIDADE_SINAL"] = "insuficiente"

    return result
