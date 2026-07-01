"""Modulo 1: Classificacao do Mercado — preenche variaveis de VOLATILIDADE."""

# Thresholds de volatilidade (movidos de config.py para evitar conflito de import)
VOL_ALTA_THRESHOLD = 1.8
VOL_BAIXA_THRESHOLD = 0.5
ATR_EXPANSAO_THRESHOLD = 1.3
ATR_COMPRESSAO_THRESHOLD = 0.7


def classify_market(candles):
    """
    Preenche ESTADO_MERCADO, VOLATILIDADE, VOL_ALTA, VOL_BAIXA,
    ATR_EXPANSAO, ATR_COMPRESSAO.

    Nunca retorna cedo — sempre calcula ATR e tendencia.
    """
    result = {
        "ESTADO_MERCADO": "indefinido",
        "VOLATILIDADE": "normal",
        "VOL_ALTA": False,
        "VOL_BAIXA": False,
        "ATR_EXPANSAO": False,
        "ATR_COMPRESSAO": False,
    }

    if not candles or len(candles) < 50:
        return result

    closes = [c[4] for c in candles]
    highs = [c[2] for c in candles]
    lows = [c[3] for c in candles]

    atr_arr = _calc_atr(highs, lows, closes, 14)
    if not atr_arr:
        return result

    atr_mean = sum(atr_arr) / len(atr_arr)
    atr_current = atr_arr[-1]
    atr_ratio = atr_current / atr_mean if atr_mean else 1.0

    result["ATR_EXPANSAO"] = atr_ratio >= ATR_EXPANSAO_THRESHOLD
    result["ATR_COMPRESSAO"] = atr_ratio <= ATR_COMPRESSAO_THRESHOLD

    if atr_ratio >= VOL_ALTA_THRESHOLD:
        result["VOL_ALTA"] = True
        result["VOLATILIDADE"] = "alta"
    elif atr_ratio <= VOL_BAIXA_THRESHOLD:
        result["VOL_BAIXA"] = True
        result["VOLATILIDADE"] = "baixa"

    # Classificacao do estado — sem early return
    recent = closes[-30:]
    returns = [
        abs(recent[i] - recent[i - 1]) / recent[i - 1]
        for i in range(1, len(recent))
    ]
    avg_move = sum(returns) / len(returns) if returns else 0

    sideways = max(recent) / min(recent) - 1 if min(recent) else 0

    if avg_move < 0.0015:
        result["ESTADO_MERCADO"] = "lateral"
    elif sideways < 0.025:
        result["ESTADO_MERCADO"] = "consolidacao"
    else:
        trend_strength = abs(closes[-1] - closes[-50]) / closes[-50]
        if trend_strength > 0.08:
            result["ESTADO_MERCADO"] = "tendencia_forte"
        elif trend_strength > 0.03:
            result["ESTADO_MERCADO"] = "tendencia_moderada"
        else:
            result["ESTADO_MERCADO"] = "micro_tendencia"

    return result


def _calc_atr(highs, lows, closes, period):
    tr = []
    for i in range(1, min(len(highs), len(lows), len(closes))):
        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i - 1])
        lc = abs(lows[i] - closes[i - 1])
        tr.append(max(hl, hc, lc))

    atr = []
    for i in range(len(tr)):
        if i < period - 1:
            continue
        atr.append(sum(tr[i - period + 1:i + 1]) / period)
    return atr
