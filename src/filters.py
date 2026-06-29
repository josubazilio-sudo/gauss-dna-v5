"""Filtros e Bloqueios — preenche variaveis FILTROS e SEGURANCA."""

from config import (
    FILTRO_LATERAL, FILTRO_VOLUME, FILTRO_FLUXO,
    FILTRO_TENDENCIA, FILTRO_LIQUIDEZ, FILTRO_MOMENTUM,
    FILTRO_VOLATILIDADE, FILTRO_SPREAD,
    ADX_MINIMO, RVOL_MINIMO,
)


def tendencia_confirmada(trend_data, flow_data, momentum_data, direcao, preco):
    """
    Regra 1 e 2 — Confirmacao de tendencia (ANTI-FUNDO / ANTI-TOPO).

    Retorna (aprovado: bool, motivo: str).
    """
    ema21 = trend_data.get("EMA_21", 0)
    ema50 = trend_data.get("EMA_50", 0)
    kalman = trend_data.get("KALMAN_DIRECAO", "")
    fluxo = flow_data.get("FLUXO_TIPO", "")
    macd_bullish = momentum_data.get("MACD_BULLISH", False)
    macd_bearish = momentum_data.get("MACD_BEARISH", False)
    macd_hist_up = momentum_data.get("MACD_HIST_CRESCENTE", False)
    ema_cruzamento = trend_data.get("EMA_CRUZAMENTO", "")

    if direcao == "long":
        if preco <= ema21:
            return False, "preco_abaixo_ema21"
        if not (ema21 > ema50 or ema_cruzamento == "bullish"):
            return False, "ema21_nao_acima_ema50"
        if kalman not in ("UP",):
            return False, "kalman_nao_alta"
        if fluxo not in ("comprador", "leve_comprador"):
            return False, "fluxo_nao_comprador"
        if not (macd_bullish or macd_hist_up):
            return False, "macd_sem_confirmacao"
        return True, ""

    if direcao == "short":
        if preco >= ema21:
            return False, "preco_acima_ema21"
        if not (ema21 < ema50 or ema_cruzamento == "bearish"):
            return False, "ema21_nao_abaixo_ema50"
        if kalman not in ("DOWN",):
            return False, "kalman_nao_baixa"
        if fluxo not in ("vendedor", "leve_vendedor"):
            return False, "fluxo_nao_vendedor"
        if not (macd_bearish or not macd_hist_up):
            return False, "macd_sem_confirmacao"
        return True, ""

    return False, "sem_direcao"


def check_filters(config, trend_data, flow_data, momentum_data, market_data, smc_data):
    """
    Preenche FILTROS_APROVADOS, FILTROS_REPROVADOS, MOTIVO_RECUSA.

    So BLOQUEIA quando for realmente grave.
    Lateral e tendencia neutra apenas registram, nao bloqueiam.
    """
    result = {
        "FILTROS_APROVADOS": [],
        "FILTROS_REPROVADOS": [],
        "MOTIVO_RECUSA": "",
    }

    # FILTRO_LATERAL — nao bloqueia mais, so registra
    if trend_data.get("TENDENCIA") == "neutra" and market_data.get("ESTADO_MERCADO") == "lateral":
        result["FILTROS_REPROVADOS"].append("FILTRO_LATERAL")
    else:
        result["FILTROS_APROVADOS"].append("FILTRO_LATERAL")

    # FILTRO_TENDENCIA — nao bloqueia mais, so registra
    if trend_data.get("TENDENCIA") == "neutra":
        result["FILTROS_REPROVADOS"].append("FILTRO_TENDENCIA")
    else:
        result["FILTROS_APROVADOS"].append("FILTRO_TENDENCIA")

    # FILTRO_VOLUME — bloqueia se RVOL extremamente baixo
    min_rvol = config.get("RVOL_MINIMO", RVOL_MINIMO)
    if flow_data.get("RVOL", 0) < min_rvol * 0.5:  # So bloqueia se < 0.5x
        result["FILTROS_REPROVADOS"].append("FILTRO_VOLUME")
        result["MOTIVO_RECUSA"] = f"rvol_muito_baixo_{flow_data.get('RVOL',0):.1f}"
        return False, result
    else:
        result["FILTROS_APROVADOS"].append("FILTRO_VOLUME")

    # FILTRO_MOMENTUM
    if config.get("FILTRO_MOMENTUM", FILTRO_MOMENTUM):
        min_adx = config.get("ADX_MINIMO", ADX_MINIMO)
        if momentum_data.get("ADX", 0) < min_adx * 0.5:  # So bloqueia se ADX < 10
            result["FILTROS_REPROVADOS"].append("FILTRO_MOMENTUM")
            result["MOTIVO_RECUSA"] = f"adx_muito_baixo_{momentum_data.get('ADX',0):.0f}"
            return False, result
        result["FILTROS_APROVADOS"].append("FILTRO_MOMENTUM")

    # FILTRO_FLUXO — so registra
    if config.get("FILTRO_FLUXO", FILTRO_FLUXO):
        if flow_data.get("DELTA") == 0:
            result["FILTROS_REPROVADOS"].append("FILTRO_FLUXO")
        else:
            result["FILTROS_APROVADOS"].append("FILTRO_FLUXO")

    # FILTRO_LIQUIDEZ — so registra
    if config.get("FILTRO_LIQUIDEZ", FILTRO_LIQUIDEZ):
        if not smc_data.get("LIQUIDITY_SWEEP") and not smc_data.get("BOS"):
            result["FILTROS_REPROVADOS"].append("FILTRO_LIQUIDEZ")
        else:
            result["FILTROS_APROVADOS"].append("FILTRO_LIQUIDEZ")

    # FILTRO_VOLATILIDADE — so bloqueia se compressao extrema
    if config.get("FILTRO_VOLATILIDADE", FILTRO_VOLATILIDADE):
        if market_data.get("ATR_COMPRESSAO") and market_data.get("ESTADO_MERCADO") in ("lateral", "consolidacao"):
            result["FILTROS_REPROVADOS"].append("FILTRO_VOLATILIDADE")
        else:
            result["FILTROS_APROVADOS"].append("FILTRO_VOLATILIDADE")

    # FILTRO_SPREAD
    if config.get("FILTRO_SPREAD", FILTRO_SPREAD):
        result["FILTROS_APROVADOS"].append("FILTRO_SPREAD")

    return True, result


def check_blockers(config, market_data, flow_data, momentum_data, trend_data):
    """
    Preenche MERCADO_PERIGOSO, STOP_CONSECUTIVO, MODO_PROTECAO, PARAR_OPERACOES.
    So para em condicoes extremas.
    """
    result = {
        "MERCADO_PERIGOSO": False,
        "STOP_CONSECUTIVO": 0,
        "MODO_PROTECAO": False,
        "PARAR_OPERACOES": False,
    }

    if market_data.get("VOL_ALTA") and flow_data.get("EXAUSTAO"):
        result["MODO_PROTECAO"] = True
        result["MERCADO_PERIGOSO"] = True

    rsi = momentum_data.get("RSI", 50)

    # So bloqueia se RSI extremo
    if rsi > 90 or rsi < 10:
        result["PARAR_OPERACOES"] = True

    if flow_data.get("ABSORCAO") and trend_data.get("TENDENCIA") == "neutra":
        result["PARAR_OPERACOES"] = True

    return result
