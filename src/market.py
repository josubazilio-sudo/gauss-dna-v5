"""Módulo 1: Classificação do Mercado."""


def classify_market(candles):
    """
    Determina o estado atual do mercado.

    Returns:
        "tendencia_forte" | "tendencia_moderada" | "consolidacao"
        | "lateral" | "alta_volatilidade" | "baixa_volatilidade"
    """
    if not candles or len(candles) < 50:
        return "lateral"

    closes = [c[4] for c in candles]
    highs = [c[2] for c in candles]
    lows = [c[3] for c in candles]

    atr = _calc_atr(highs, lows, closes, 14)
    atr_mean = sum(atr) / len(atr) if atr else 0
    atr_pct = atr[-1] / atr_mean if atr_mean else 0

    if atr_pct > 1.8:
        return "alta_volatilidade"
    if atr_pct < 0.5:
        return "baixa_volatilidade"

    returns = [abs(closes[i] - closes[i - 1]) / closes[i - 1]
               for i in range(1, len(closes[-30:]))]
    avg_move = sum(returns) / len(returns) if returns else 0

    if avg_move < 0.002:
        return "lateral"

    recent = closes[-20:]
    sideways = max(recent) / min(recent) - 1
    if sideways < 0.03:
        return "consolidacao"

    trend_strength = abs(closes[-1] - closes[-50]) / closes[-50]
    if trend_strength > 0.08:
        return "tendencia_forte"
    if trend_strength > 0.03:
        return "tendencia_moderada"

    return "lateral"


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
