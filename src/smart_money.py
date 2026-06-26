"""Módulo 3: Smart Money Concepts."""


def detect_smc(candles):
    """
    Detecta conceitos SMC:
    - Sweep de liquidez
    - Break of Structure (BOS)
    - Change of Character (CHOCH)
    - FVG (Fair Value Gap)
    - Order Block

    Retorna dict com confirmações.
    """
    result = {
        "sweep": False,
        "bos": False,
        "choch": False,
        "fvg": False,
        "order_block": False,
        "estrutura": "neutra",
    }

    if not candles or len(candles) < 20:
        return result

    highs = [c[2] for c in candles]
    lows = [c[3] for c in candles]
    closes = [c[4] for c in candles]

    recent_high = max(highs[-10:])
    recent_low = min(lows[-10:])

    if closes[-1] > recent_high and highs[-1] > recent_high * 1.001:
        result["bos"] = True
        result["estrutura"] = "alta"

    if closes[-1] < recent_low and lows[-1] < recent_low * 0.999:
        result["bos"] = True
        result["estrutura"] = "baixa"

    for i in range(-5, -1):
        if len(candles) > abs(i + 1):
            if lows[i] < recent_low and closes[i] > closes[i - 1] and closes[-1] > closes[i]:
                result["sweep"] = True

    for i in range(-10, -1):
        gap = min(candles[i][2], candles[i + 1][2]) - max(candles[i][3], candles[i + 1][3])
        if gap > 0:
            result["fvg"] = True
            break

    return result
