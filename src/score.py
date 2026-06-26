"""Score Institucional — preenche variaveis SCORE e CLASSIFICACAO."""

from config import (
    PESO_TENDENCIA, PESO_FLUXO, PESO_VOLUME, PESO_LIQUIDEZ,
    PESO_ESTRUTURA, PESO_MOMENTUM, PESO_VOLATILIDADE,
    PESO_MULTI_TIMEFRAME,
    SCORE_OURO_MIN, SCORE_PRATA_MIN, SCORE_BRONZE_MIN,
)


def calculate_score(config, trend_data, flow_data, smc_data, momentum_data, market_data, mtf_bonus=0):
    """
    Preenche SCORE_TENDENCIA, SCORE_VOLUME, SCORE_FLUXO,
    SCORE_MOMENTUM, SCORE_LIQUIDEZ, SCORE_ESTRUTURA,
    SCORE_VOLATILIDADE, SCORE_TOTAL.
    Mais liberal que a versao original.
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

    p_tend = config.get("PESO_TENDENCIA", PESO_TENDENCIA)
    p_fluxo = config.get("PESO_FLUXO", PESO_FLUXO)
    p_vol = config.get("PESO_VOLUME", PESO_VOLUME)
    p_mom = config.get("PESO_MOMENTUM", PESO_MOMENTUM)
    p_liq = config.get("PESO_LIQUIDEZ", PESO_LIQUIDEZ)
    p_est = config.get("PESO_ESTRUTURA", PESO_ESTRUTURA)
    p_volat = config.get("PESO_VOLATILIDADE", PESO_VOLATILIDADE)

    # Tendencia (peso cheio se nao for neutra)
    tend = trend_data.get("TENDENCIA", "neutra")
    if tend in ("alta", "alta_moderada"):
        result["SCORE_TENDENCIA"] = p_tend
    elif tend in ("baixa", "baixa_moderada"):
        result["SCORE_TENDENCIA"] = p_tend
    elif trend_data.get("EMA_ALINHADA"):
        result["SCORE_TENDENCIA"] = p_tend // 2
    else:
        result["SCORE_TENDENCIA"] = p_tend // 3

    if trend_data.get("EMA_CRUZAMENTO") in ("bullish", "bearish"):
        result["SCORE_TENDENCIA"] = min(result["SCORE_TENDENCIA"] + 5, p_tend)

    # Fluxo (parcial se delta existir, cheio se alinhado com direcao)
    delta = flow_data.get("DELTA", 0)
    direcao = trend_data.get("DIRECAO", "lateral")
    if delta > 0 and direcao == "long":
        result["SCORE_FLUXO"] = p_fluxo
    elif delta < 0 and direcao == "short":
        result["SCORE_FLUXO"] = p_fluxo
    elif delta != 0:
        result["SCORE_FLUXO"] = p_fluxo // 2
    else:
        result["SCORE_FLUXO"] = p_fluxo // 4

    # Volume (parcial se RVOL > 0.7, cheio se > 1.0)
    rvol = flow_data.get("RVOL", 0)
    if rvol >= 1.0:
        result["SCORE_VOLUME"] = p_vol
    elif rvol >= 0.7:
        result["SCORE_VOLUME"] = p_vol // 2
    else:
        result["SCORE_VOLUME"] = p_vol // 4

    if flow_data.get("VOLUME_CRESCENTE"):
        result["SCORE_VOLUME"] = min(result["SCORE_VOLUME"] + 5, p_vol)

    # Momentum
    adx = momentum_data.get("ADX", 0)
    if adx >= 20:
        result["SCORE_MOMENTUM"] = p_mom
    elif adx >= 15:
        result["SCORE_MOMENTUM"] = p_mom // 2
    else:
        result["SCORE_MOMENTUM"] = p_mom // 4

    mom = momentum_data.get("MOMENTUM", "neutro")
    if mom == "crescente" and direcao == "long":
        result["SCORE_MOMENTUM"] = min(result["SCORE_MOMENTUM"] + 5, p_mom)
    elif mom == "decrescente" and direcao == "short":
        result["SCORE_MOMENTUM"] = min(result["SCORE_MOMENTUM"] + 5, p_mom)

    # Liquidez
    if smc_data.get("LIQUIDITY_SWEEP") or smc_data.get("STOP_HUNT"):
        result["SCORE_LIQUIDEZ"] = p_liq
    elif smc_data.get("ORDER_BLOCK") or smc_data.get("FVG"):
        result["SCORE_LIQUIDEZ"] = p_liq // 2
    else:
        result["SCORE_LIQUIDEZ"] = p_liq // 3

    if smc_data.get("RETESTE"):
        result["SCORE_LIQUIDEZ"] = min(result["SCORE_LIQUIDEZ"] + 5, p_liq)

    # Estrutura
    if smc_data.get("BOS"):
        result["SCORE_ESTRUTURA"] = p_est
    elif smc_data.get("CHOCH"):
        result["SCORE_ESTRUTURA"] = p_est // 2
    else:
        result["SCORE_ESTRUTURA"] = p_est // 3

    if smc_data.get("ESTRUTURA_OK"):
        result["SCORE_ESTRUTURA"] = min(result["SCORE_ESTRUTURA"] + 5, p_est)

    # Volatilidade
    if market_data.get("ATR_EXPANSAO") or market_data.get("VOL_ALTA"):
        result["SCORE_VOLATILIDADE"] = p_volat
    elif not market_data.get("ATR_COMPRESSAO"):
        result["SCORE_VOLATILIDADE"] = p_volat // 2

    # Soma + bonus multi-timeframe
    total = sum([
        result["SCORE_TENDENCIA"],
        result["SCORE_FLUXO"],
        result["SCORE_VOLUME"],
        result["SCORE_MOMENTUM"],
        result["SCORE_LIQUIDEZ"],
        result["SCORE_ESTRUTURA"],
        result["SCORE_VOLATILIDADE"],
    ])
    total += mtf_bonus
    result["SCORE_TOTAL"] = min(total, 100)

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
