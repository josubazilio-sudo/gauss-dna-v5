"""Filtros e Bloqueios — preenche variáveis FILTROS e SEGURANÇA."""

from config import (
    FILTRO_LATERAL, FILTRO_VOLUME, FILTRO_FLUXO,
    FILTRO_TENDENCIA, FILTRO_LIQUIDEZ, FILTRO_MOMENTUM,
    FILTRO_VOLATILIDADE, FILTRO_SPREAD,
    ADX_MINIMO, RVOL_MINIMO,
)


def check_filters(config, trend_data, flow_data, momentum_data, market_data, smc_data):
    """
    Preenche FILTROS_APROVADOS, FILTROS_REPROVADOS, MOTIVO_RECUSA.

    Returns (passed: bool, result: dict)
    """
    result = {
        "FILTROS_APROVADOS": [],
        "FILTROS_REPROVADOS": [],
        "MOTIVO_RECUSA": "",
    }
    passed = True

    # FILTRO_LATERAL
    if config.get("FILTRO_LATERAL", FILTRO_LATERAL):
        if market_data.get("ESTADO_MERCADO") == "lateral":
            result["FILTROS_REPROVADOS"].append("FILTRO_LATERAL")
            result["MOTIVO_RECUSA"] = "mercado_lateral"
            return False, result
        result["FILTROS_APROVADOS"].append("FILTRO_LATERAL")

    # FILTRO_TENDENCIA
    if config.get("FILTRO_TENDENCIA", FILTRO_TENDENCIA):
        if trend_data.get("TENDENCIA") == "neutra":
            result["FILTROS_REPROVADOS"].append("FILTRO_TENDENCIA")
            result["MOTIVO_RECUSA"] = "tendencia_neutra"
            return False, result
        result["FILTROS_APROVADOS"].append("FILTRO_TENDENCIA")

    # FILTRO_VOLUME
    if config.get("FILTRO_VOLUME", FILTRO_VOLUME):
        min_rvol = config.get("RVOL_MINIMO", RVOL_MINIMO)
        if flow_data.get("RVOL", 0) < min_rvol:
            result["FILTROS_REPROVADOS"].append("FILTRO_VOLUME")
            result["MOTIVO_RECUSA"] = f"rvol_baixo_{flow_data.get('RVOL',0):.1f}"
            return False, result
        result["FILTROS_APROVADOS"].append("FILTRO_VOLUME")

    # FILTRO_MOMENTUM
    if config.get("FILTRO_MOMENTUM", FILTRO_MOMENTUM):
        min_adx = config.get("ADX_MINIMO", ADX_MINIMO)
        if momentum_data.get("ADX", 0) < min_adx:
            result["FILTROS_REPROVADOS"].append("FILTRO_MOMENTUM")
            result["MOTIVO_RECUSA"] = f"adx_baixo_{momentum_data.get('ADX',0):.0f}"
            return False, result
        result["FILTROS_APROVADOS"].append("FILTRO_MOMENTUM")

    # FILTRO_FLUXO
    if config.get("FILTRO_FLUXO", FILTRO_FLUXO):
        if flow_data.get("DELTA") == 0:
            result["FILTROS_REPROVADOS"].append("FILTRO_FLUXO")
            result["MOTIVO_RECUSA"] = "fluxo_neutro"
            return False, result
        result["FILTROS_APROVADOS"].append("FILTRO_FLUXO")

    # FILTRO_LIQUIDEZ
    if config.get("FILTRO_LIQUIDEZ", FILTRO_LIQUIDEZ):
        if not smc_data.get("LIQUIDITY_SWEEP") and not smc_data.get("BOS"):
            result["FILTROS_REPROVADOS"].append("FILTRO_LIQUIDEZ")
            result["MOTIVO_RECUSA"] = "sem_liquidez"
            result["FILTROS_APROVADOS"].append("FILTRO_LIQUIDEZ")

    # FILTRO_VOLATILIDADE
    if config.get("FILTRO_VOLATILIDADE", FILTRO_VOLATILIDADE):
        if market_data.get("ATR_COMPRESSAO"):
            result["FILTROS_REPROVADOS"].append("FILTRO_VOLATILIDADE")
            result["MOTIVO_RECUSA"] = "atr_comprimido"
            return False, result
        result["FILTROS_APROVADOS"].append("FILTRO_VOLATILIDADE")

    # FILTRO_SPREAD
    if config.get("FILTRO_SPREAD", FILTRO_SPREAD):
        result["FILTROS_APROVADOS"].append("FILTRO_SPREAD")

    return True, result


def check_blockers(config, market_data, flow_data, momentum_data, trend_data):
    """
    Preenche MERCADO_PERIGOSO, STOP_CONSECUTIVO, MODO_PROTECAO, PARAR_OPERACOES.
    """
    result = {
        "MERCADO_PERIGOSO": False,
        "STOP_CONSECUTIVO": 0,
        "MODO_PROTECAO": False,
        "PARAR_OPERACOES": False,
    }

    if market_data.get("VOL_ALTA"):
        result["MERCADO_PERIGOSO"] = True

    if flow_data.get("EXAUSTAO"):
        result["MODO_PROTECAO"] = True

    rsi = momentum_data.get("RSI", 50)
    rsi_long_max = config.get("RSI_LONG_MAX", 80)
    rsi_short_min = config.get("RSI_SHORT_MIN", 20)

    if momentum_data.get("RSI_LONG") and trend_data.get("DIRECAO") == "long":
        pass
    elif momentum_data.get("RSI_SHORT") and trend_data.get("DIRECAO") == "short":
        pass
    elif rsi > rsi_long_max or rsi < rsi_short_min:
        result["PARAR_OPERACOES"] = True

    if flow_data.get("ABSORCAO") and trend_data.get("TENDENCIA") == "neutra":
        result["PARAR_OPERACOES"] = True

    return result
