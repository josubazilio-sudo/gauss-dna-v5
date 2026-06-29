"""Filtros e Bloqueios — V7.3: Score-based com minimos bloqueios rigidos."""

from config import (
    FILTRO_LATERAL, RVOL_MINIMO, ADX_MINIMO,
)


def tendencia_adaptativa(trend_data, flow_data, momentum_data, direcao, preco):
    """
    V7.3 — Filtro de tendencia adaptativo (baseado em pontuacao).

    Retorna (pontos, motivo, bloqueado).
    """
    ema21 = trend_data.get("EMA_21", 0)
    ema50 = trend_data.get("EMA_50", 0)
    kalman = trend_data.get("KALMAN_DIRECAO", "")
    fluxo = flow_data.get("FLUXO_TIPO", "")
    macd_bullish = momentum_data.get("MACD_BULLISH", False)
    macd_bearish = momentum_data.get("MACD_BEARISH", False)
    macd_hist_up = momentum_data.get("MACD_HIST_CRESCENTE", False)
    ema_cruzamento = trend_data.get("EMA_CRUZAMENTO", "")
    adx = momentum_data.get("ADX", 0)

    if direcao == "long":
        totalmente_alinhado = (
            preco and ema21 and preco > ema21 and ema21 and ema50 and ema21 > ema50
            and kalman == "UP"
            and fluxo in ("comprador", "leve_comprador")
        )
        if totalmente_alinhado:
            return 10, "tendencia_alinhada", False

        contra_tendencia = (
            kalman == "DOWN"
            and fluxo in ("vendedor", "leve_vendedor")
        )
        if contra_tendencia:
            return 0, "tendencia_contraria", True

        parcial = 0
        if ema_cruzamento == "bullish" or (macd_bullish or macd_hist_up):
            parcial += 3
        if kalman == "UP":
            parcial += 3
        if adx and adx >= ADX_MINIMO and momentum_data.get("MOMENTUM") == "crescente":
            parcial += 2
        if fluxo in ("comprador", "leve_comprador"):
            parcial += 2
        if preco and ema21 and preco > ema21:
            parcial += 1
        return min(parcial, 8), "tendencia_parcial", False

    if direcao == "short":
        totalmente_alinhado = (
            preco and ema21 and preco < ema21 and ema21 and ema50 and ema21 < ema50
            and kalman == "DOWN"
            and fluxo in ("vendedor", "leve_vendedor")
        )
        if totalmente_alinhado:
            return 10, "tendencia_alinhada", False

        contra_tendencia = (
            kalman == "UP"
            and fluxo in ("comprador", "leve_comprador")
        )
        if contra_tendencia:
            return 0, "tendencia_contraria", True

        parcial = 0
        if ema_cruzamento == "bearish" or (macd_bearish or not macd_hist_up):
            parcial += 3
        if kalman == "DOWN":
            parcial += 3
        if adx and adx >= ADX_MINIMO and momentum_data.get("MOMENTUM") == "crescente":
            parcial += 2
        if fluxo in ("vendedor", "leve_vendedor"):
            parcial += 2
        if preco and ema21 and preco < ema21:
            parcial += 1
        return min(parcial, 8), "tendencia_parcial", False

    return 0, "sem_direcao", True


def check_filters(config, trend_data, flow_data, momentum_data, market_data, smc_data):
    """
    V7.3 — Filtros baseados em score.

    Nao bloqueia mais por RVOL, ADX ou tendencia neutra sozinhos.
    Apenas bloqueia por seguranca (circuit breaker, volatilidade extrema).
    """
    result = {
        "FILTROS_APROVADOS": [],
        "FILTROS_REPROVADOS": [],
        "MOTIVO_RECUSA": "",
    }

    if market_data.get("VOL_ALTA") and flow_data.get("EXAUSTAO"):
        result["FILTROS_REPROVADOS"].append("FILTRO_VOLATILIDADE_EXAUSTAO")
        result["MOTIVO_RECUSA"] = "volatilidade_exaustao"
        return False, result

    if flow_data.get("ABSORCAO") and trend_data.get("TENDENCIA") == "neutra":
        result["FILTROS_REPROVADOS"].append("FILTRO_ABSORCAO_NEUTRO")
        result["MOTIVO_RECUSA"] = "absorcao_mercado_lateral"
        return False, result

    rsi = momentum_data.get("RSI", 50)
    if rsi > 90 or rsi < 10:
        result["FILTROS_REPROVADOS"].append("FILTRO_RSI_EXTREMO")
        result["MOTIVO_RECUSA"] = "rsi_extremo"
        return False, result

    result["FILTROS_APROVADOS"].append("FILTRO_VOLUME")
    result["FILTROS_APROVADOS"].append("FILTRO_MOMENTUM")
    result["FILTROS_APROVADOS"].append("FILTRO_FLUXO")
    result["FILTROS_APROVADOS"].append("FILTRO_LIQUIDEZ")
    result["FILTROS_APROVADOS"].append("FILTRO_LATERAL")
    result["FILTROS_APROVADOS"].append("FILTRO_TENDENCIA")
    result["FILTROS_APROVADOS"].append("FILTRO_VOLATILIDADE")
    result["FILTROS_APROVADOS"].append("FILTRO_SPREAD")

    return True, result


def check_blockers(config, market_data, flow_data, momentum_data, trend_data):
    """
    Preenche MERCADO_PERIGOSO, STOP_CONSECUTIVO, MODO_PROTECAO, PARAR_OPERACOES.
    Apenas para condicoes extremas.
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
    if rsi > 90 or rsi < 10:
        result["PARAR_OPERACOES"] = True

    if flow_data.get("ABSORCAO") and trend_data.get("TENDENCIA") == "neutra":
        result["PARAR_OPERACOES"] = True

    return result


def confirmacao_disparo(trend_data, flow_data, momentum_data, smc_data, direcao, preco):
    """
    V7.3 Regra 6 — Confirmacao antes do disparo.

    Retorna (aprovado: bool, motivo: str, detalhes: list).
    """
    detalhes = []
    kalman = trend_data.get("KALMAN_DIRECAO", "")
    fluxo = flow_data.get("FLUXO_TIPO", "")
    macd_bullish = momentum_data.get("MACD_BULLISH", False)
    macd_bearish = momentum_data.get("MACD_BEARISH", False)
    macd_hist_up = momentum_data.get("MACD_HIST_CRESCENTE", False)
    bos = smc_data.get("BOS", False)
    ema21 = trend_data.get("EMA_21", 0)

    if direcao == "long":
        if fluxo in ("comprador", "leve_comprador"):
            detalhes.append("fluxo_comprador")
        else:
            detalhes.append("fluxo_sem_compra")
        if kalman in ("UP",):
            detalhes.append("kalman_alta")
        else:
            detalhes.append("kalman_sem_alta")
        if macd_bullish or macd_hist_up:
            detalhes.append("macd_positivo")
        else:
            detalhes.append("macd_sem_positivo")
        if preco and ema21 and preco > ema21:
            detalhes.append("candle_confirmado")
        else:
            detalhes.append("candle_sem_confirmacao")
        if bos:
            detalhes.append("estrutura_alta")
        else:
            detalhes.append("estrutura_sem_alta")

        falhas = sum(1 for d in detalhes if "sem_" in d)
        return falhas <= 2, "confirmacao_long" if falhas <= 2 else "falta_confirmacao_long", detalhes

    if direcao == "short":
        if fluxo in ("vendedor", "leve_vendedor"):
            detalhes.append("fluxo_vendedor")
        else:
            detalhes.append("fluxo_sem_venda")
        if kalman in ("DOWN",):
            detalhes.append("kalman_baixa")
        else:
            detalhes.append("kalman_sem_baixa")
        if macd_bearish or not macd_hist_up:
            detalhes.append("macd_negativo")
        else:
            detalhes.append("macd_sem_negativo")
        if preco and ema21 and preco < ema21:
            detalhes.append("candle_confirmado")
        else:
            detalhes.append("candle_sem_confirmacao")
        if bos:
            detalhes.append("estrutura_baixa")
        else:
            detalhes.append("estrutura_sem_baixa")

        falhas = sum(1 for d in detalhes if "sem_" in d)
        return falhas <= 2, "confirmacao_short" if falhas <= 2 else "falta_confirmacao_short", detalhes

    return False, "sem_direcao", []
