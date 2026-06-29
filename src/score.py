"""Score Institucional — V7.3: Score por Pesos."""

from config import (
    PESO_TENDENCIA, PESO_FLUXO, PESO_VOLUME,
    PESO_MOMENTUM, PESO_ESTRUTURA, PESO_LIQUIDEZ,
    PESO_MULTI_TIMEFRAME,
    SCORE_OURO_SUPREMO_MIN, SCORE_OURO_MIN, SCORE_PRATA_MIN, SCORE_BRONZE_MIN,
    ADX_ALTO, ADX_MEDIO, ADX_BAIXO,
    RVOL_FORTE, RVOL_MODERADO, RVOL_FRACO,
)


def _score_tendencia(trend_data, direcao):
    tend = trend_data.get("TENDENCIA", "neutra")
    if direcao == "long":
        if tend in ("alta",):
            return PESO_TENDENCIA
        if tend in ("alta_moderada",):
            return PESO_TENDENCIA - 5
        return PESO_TENDENCIA // 2
    elif direcao == "short":
        if tend in ("baixa",):
            return PESO_TENDENCIA
        if tend in ("baixa_moderada",):
            return PESO_TENDENCIA - 5
        return PESO_TENDENCIA // 2

    ema_alinhada = trend_data.get("EMA_ALINHADA", False)
    if ema_alinhada:
        return PESO_TENDENCIA // 2
    return PESO_TENDENCIA // 3


def _score_fluxo(flow_data, direcao):
    delta = flow_data.get("DELTA", 0)
    fluxo_tipo = flow_data.get("FLUXO_TIPO", "")
    volume = flow_data.get("VOLUME", 0)
    volume_medio = flow_data.get("VOLUME_MEDIO", 1)

    if direcao == "long":
        if delta > 0 and fluxo_tipo in ("comprador",):
            return PESO_FLUXO
        if delta > 0:
            return PESO_FLUXO - 5
        if volume > volume_medio * 1.5 and delta > 0:
            return PESO_FLUXO - 3
        return PESO_FLUXO // 2

    if direcao == "short":
        if delta < 0 and fluxo_tipo in ("vendedor",):
            return PESO_FLUXO
        if delta < 0:
            return PESO_FLUXO - 5
        if volume > volume_medio * 1.5 and delta < 0:
            return PESO_FLUXO - 3
        return PESO_FLUXO // 2

    return PESO_FLUXO // 3


def _score_volume(flow_data, mercado_estado):
    rvol = flow_data.get("RVOL", 0)

    if mercado_estado in ("tendencia_forte",):
        rvol_min = RVOL_FORTE
    elif mercado_estado in ("tendencia_moderada", "micro_tendencia"):
        rvol_min = RVOL_MODERADO
    else:
        rvol_min = RVOL_FRACO

    if rvol >= rvol_min * 2:
        return PESO_VOLUME
    if rvol >= rvol_min * 1.5:
        return PESO_VOLUME - 3
    if rvol >= rvol_min:
        return PESO_VOLUME - 6
    if rvol >= rvol_min * 0.7:
        return PESO_VOLUME - 9

    return PESO_VOLUME // 2


def _score_momentum(momentum_data, mercado_estado):
    adx = momentum_data.get("ADX", 0)
    adx_crescente = momentum_data.get("MOMENTUM") == "crescente"
    ha_bull = momentum_data.get("HA_BULL", False)
    ha_bear = momentum_data.get("HA_BEAR", False)

    pontos = 0

    if adx >= ADX_ALTO:
        pontos = 10
    elif adx >= ADX_MEDIO:
        pontos = 7
    elif adx >= ADX_BAIXO:
        pontos = 4
    elif mercado_estado in ("tendencia_forte", "tendencia_moderada"):
        pontos = 3
    else:
        pontos = 3

    if adx_crescente:
        pontos += 2

    ha_alinhado = (ha_bull or ha_bear)
    if ha_alinhado:
        pontos += 3

    return min(pontos, PESO_MOMENTUM)


def _score_estrutura(smc_data):
    bos = smc_data.get("BOS", False)
    choch = smc_data.get("CHOCH", False)
    estrutura_ok = smc_data.get("ESTRUTURA_OK", False)
    liquidity = smc_data.get("LIQUIDITY_SWEEP", False)

    if bos and estrutura_ok:
        return PESO_ESTRUTURA
    if bos or choch:
        return PESO_ESTRUTURA - 2
    if liquidity:
        return PESO_ESTRUTURA - 4
    return PESO_ESTRUTURA - 5


def _score_liquidez(smc_data):
    liquidity = smc_data.get("LIQUIDITY_SWEEP", False)
    order_block = smc_data.get("ORDER_BLOCK", False)
    fvg = smc_data.get("FVG", False)
    mitigacao = smc_data.get("MITIGACAO", False)

    if liquidity or (order_block and fvg):
        return PESO_LIQUIDEZ
    if order_block or fvg:
        return PESO_LIQUIDEZ - 3
    if mitigacao:
        return PESO_LIQUIDEZ - 5
    return PESO_LIQUIDEZ - 6


def calculate_score(config, trend_data, flow_data, smc_data, momentum_data, market_data, mtf_bonus=0, preco=0, direcao=None):
    """
    V7.3 — Score por pesos.

    Cada componente contribui com seu peso maximo.
    Bloqueios rigidos foram substituidos por reducao de pontos.
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

    if direcao not in ("long", "short"):
        mercado_estado = market_data.get("ESTADO_MERCADO", "")
        result["SCORE_TENDENCIA"] = _score_tendencia(trend_data, None)
        result["SCORE_FLUXO"] = PESO_FLUXO // 3
        result["SCORE_VOLUME"] = _score_volume(flow_data, mercado_estado)
        result["SCORE_MOMENTUM"] = _score_momentum(momentum_data, mercado_estado)
        result["SCORE_ESTRUTURA"] = _score_estrutura(smc_data)
        result["SCORE_LIQUIDEZ"] = _score_liquidez(smc_data)
        total = sum(v for k, v in result.items() if k != "SCORE_TOTAL")
        total += mtf_bonus
        result["SCORE_TOTAL"] = min(total, 100)
        return result

    mercado_estado = market_data.get("ESTADO_MERCADO", "")

    result["SCORE_TENDENCIA"] = _score_tendencia(trend_data, direcao)
    result["SCORE_FLUXO"] = _score_fluxo(flow_data, direcao)
    result["SCORE_VOLUME"] = _score_volume(flow_data, mercado_estado)
    result["SCORE_MOMENTUM"] = _score_momentum(momentum_data, mercado_estado)
    result["SCORE_ESTRUTURA"] = _score_estrutura(smc_data)
    result["SCORE_LIQUIDEZ"] = _score_liquidez(smc_data)

    bonus = 0
    kalman = trend_data.get("KALMAN_DIRECAO", "")
    fluxo = flow_data.get("FLUXO_TIPO", "")
    ema21 = trend_data.get("EMA_21", 0)
    macd_bullish = momentum_data.get("MACD_BULLISH", False)
    macd_bearish = momentum_data.get("MACD_BEARISH", False)
    macd_hist_up = momentum_data.get("MACD_HIST_CRESCENTE", False)

    if direcao == "long":
        if kalman == "UP" and fluxo in ("comprador", "leve_comprador"):
            bonus += 3
        if preco is not None and ema21 is not None and preco > ema21:
            bonus += 2
        if macd_bullish or macd_hist_up:
            bonus += 2
    elif direcao == "short":
        if kalman == "DOWN" and fluxo in ("vendedor", "leve_vendedor"):
            bonus += 3
        if preco is not None and ema21 is not None and preco < ema21:
            bonus += 2
        if macd_bearish or not macd_hist_up:
            bonus += 2

    total = sum([
        result["SCORE_TENDENCIA"],
        result["SCORE_FLUXO"],
        result["SCORE_VOLUME"],
        result["SCORE_MOMENTUM"],
        result["SCORE_ESTRUTURA"],
        result["SCORE_LIQUIDEZ"],
    ])
    total += mtf_bonus
    total += bonus
    result["SCORE_TOTAL"] = min(total, 100)

    return result


def classify_signal(score_total, confianca=100):
    """
    V7.3 — Nova classificacao.

    Bronze: 55-64
    Prata: 65-79
    Ouro: 80-89
    Ouro Supremo: 90+
    """
    result = {
        "SINAL_OURO_SUPREMO": False,
        "SINAL_OURO": False,
        "SINAL_PRATA": False,
        "SINAL_BRONZE": False,
        "NIVEL_CONFIANCA": confianca,
        "QUALIDADE_SINAL": "",
        "CLASSIFICACAO_FINAL": "",
    }

    if score_total >= SCORE_OURO_SUPREMO_MIN:
        result["SINAL_OURO_SUPREMO"] = True
        result["CLASSIFICACAO_FINAL"] = "OURO_SUPREMO"
        result["QUALIDADE_SINAL"] = "excelente"
    elif score_total >= SCORE_OURO_MIN:
        result["SINAL_OURO"] = True
        result["CLASSIFICACAO_FINAL"] = "OURO"
        result["QUALIDADE_SINAL"] = "otima"
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
