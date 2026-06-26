"""Módulo 2: Análise de Tendência com Médias Móveis."""


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
    Analisa tendência usando MM10, MM21, MM50, MM200.
    """
    closes = [c[4] for c in candles]
    if len(closes) < 200:
        return "neutra", {}

    mm10 = ema(closes, 10)
    mm21 = ema(closes, 21)
    mm50 = ema(closes, 50)
    mm200 = ema(closes, 200)

    if not all([mm10, mm21, mm50, mm200]):
        return "neutra", {}

    c = closes[-1]
    m10 = mm10[-1]
    m21 = mm21[-1]
    m50 = mm50[-1]
    m200 = mm200[-1]

    bullish = (c > m200 and m10 > m21 > m50 > m200)
    bearish = (c < m200 and m10 < m21 < m50 < m200)

    if bullish and (m10 - m21) / m21 > 0.005:
        return "muito_forte", {"mm10": m10, "mm21": m21, "mm50": m50, "mm200": m200}
    if bullish:
        return "forte", {"mm10": m10, "mm21": m21, "mm50": m50, "mm200": m200}

    if bearish and (m21 - m10) / m21 > 0.005:
        return "muito_forte", {"mm10": m10, "mm21": m21, "mm50": m50, "mm200": m200}
    if bearish:
        return "forte", {"mm10": m10, "mm21": m21, "mm50": m50, "mm200": m200}

    return "neutra", {"mm10": m10, "mm21": m21, "mm50": m50, "mm200": m200}
