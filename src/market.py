"""Módulo 1: Classificação do Mercado — preenche variáveis de VOLATILIDADE."""

from config import VOL_ALTA_THRESHOLD, VOL_BAIXA_THRESHOLD, ATR_EXPANSAO_THRESHOLD, ATR_COMPRESSAO_THRESHOLD


def classify_market(candles):
    """
    Preenche VOLATILIDADE, VOL_ALTA, VOL_BAIXA, ATR_EXPANSAO, ATR_COMPRESSAO.

    Returns dict com chaves: ESTADO_MERCADO, VOLATILIDADE, VOL_ALTA, VOL_BAIXA,
    ATR_EXPANSAO, ATR_COMPRESSAO
    """
    result = {
        "ESTADO_MERCADO": "lateral",
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

    returns = [
        abs(closes[i] - closes[i - 1]) / closes[i - 1]
        for i in range(1, len(closes[-30:]))
    ]
    avg_move = sum(returns) / len(returns) if returns else 0

    if avg_move < 0.002:
        result["ESTADO_MERCADO"] = "lateral"
        return result

    recent = closes[-20:]
    sideways = max(recent) / min(recent) - 1
    if sideways < 0.03:
        result["ESTADO_MERCADO"] = "consolidacao"
        return result

    trend_strength = abs(closes[-1] - closes[-50]) / closes[-50]
    if trend_strength > 0.08:
        result["ESTADO_MERCADO"] = "tendencia_forte"
    elif trend_strength > 0.03:
        result["ESTADO_MERCADO"] = "tendencia_moderada"

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
