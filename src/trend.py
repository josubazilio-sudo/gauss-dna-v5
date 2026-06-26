"""Módulo 2: Análise de Tendência — preenche variáveis TENDÊNCIA."""


def ema(data, period):
    if len(data) < period:
        return None
    k = 2 / (period + 1)
    result = [sum(data[:period]) / period]
    for price in data[period:]:
        result.append(price * k + result[-1] * (1 - k))
    return result


def analyze_trend(candles):
    """
    Preenche EMA_10, EMA_21, EMA_50, EMA_200, EMA_ALINHADA,
    EMA_CRUZAMENTO, EMA_FORCA, EMA_INCLINACAO, TENDENCIA, DIRECAO.
    """
    closes = [c[4] for c in candles]

    result = {
        "EMA_10": None, "EMA_21": None, "EMA_50": None, "EMA_200": None,
        "EMA_ALINHADA": False, "EMA_CRUZAMENTO": "", "EMA_FORCA": "",
        "EMA_INCLINACAO": "", "TENDENCIA": "neutra", "DIRECAO": "lateral",
    }

    mm10 = ema(closes, 10)
    mm21 = ema(closes, 21)
    mm50 = ema(closes, 50)
    mm200 = ema(closes, 200)

    if not all([mm10, mm21, mm50, mm200]):
        return result

    c = closes[-1]
    m10 = mm10[-1]
    m21 = mm21[-1]
    m50 = mm50[-1]
    m200 = mm200[-1]

    result["EMA_10"] = m10
    result["EMA_21"] = m21
    result["EMA_50"] = m50
    result["EMA_200"] = m200

    # Alinhamento
    result["EMA_ALINHADA"] = (m10 > m21 > m50 > m200) or (m10 < m21 < m50 < m200)

    # Cruzamento
    if mm10[-2] <= m21 < m10 and mm10[-1] > mm21[-1]:
        result["EMA_CRUZAMENTO"] = "bullish"
    elif mm10[-2] >= m21 > m10 and mm10[-1] < mm21[-1]:
        result["EMA_CRUZAMENTO"] = "bearish"

    # Inclinação
    ema10_slope = (mm10[-1] - mm10[-5]) / mm10[-5] if len(mm10) >= 5 else 0
    result["EMA_INCLINACAO"] = "subindo" if ema10_slope > 0 else "descendo"

    # Força
    dist_pct = abs(m10 - m21) / m21
    if dist_pct > 0.005:
        result["EMA_FORCA"] = "forte"
    elif dist_pct > 0.002:
        result["EMA_FORCA"] = "moderada"
    else:
        result["EMA_FORCA"] = "fraca"

    # Tendência
    if c > m200 and m10 > m21 > m50 > m200:
        result["TENDENCIA"] = "alta"
        result["DIRECAO"] = "long"
    elif c < m200 and m10 < m21 < m50 < m200:
        result["TENDENCIA"] = "baixa"
        result["DIRECAO"] = "short"
    elif c > m200 and m10 > m21:
        result["TENDENCIA"] = "alta_moderada"
        result["DIRECAO"] = "long"
    elif c < m200 and m10 < m21:
        result["TENDENCIA"] = "baixa_moderada"
        result["DIRECAO"] = "short"
    else:
        result["TENDENCIA"] = "neutra"
        result["DIRECAO"] = "lateral"

    return result
