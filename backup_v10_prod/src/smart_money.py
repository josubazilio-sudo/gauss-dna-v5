"""Módulo 3: Smart Money Concepts — preenche variáveis SMART MONEY."""

from config import SMC_SWEEP_LOOKBACK, SMC_BOS_CONFIRMACAO


def detect_smc(candles):
    """
    Preenche BOS, CHOCH, LIQUIDITY_SWEEP, STOP_HUNT,
    ORDER_BLOCK, FVG, MITIGACAO, RETESTE, ESTRUTURA_OK.
    """
    result = {
        "BOS": False,
        "CHOCH": False,
        "LIQUIDITY_SWEEP": False,
        "STOP_HUNT": False,
        "ORDER_BLOCK": False,
        "FVG": False,
        "MITIGACAO": False,
        "RETESTE": False,
        "ESTRUTURA_OK": False,
    }

    if not candles or len(candles) < 20:
        return result

    highs = [c[2] for c in candles]
    lows = [c[3] for c in candles]
    opens = [c[1] for c in candles]
    closes = [c[4] for c in candles]

    recent_high = max(highs[-SMC_SWEEP_LOOKBACK:])
    recent_low = min(lows[-SMC_SWEEP_LOOKBACK:])
    prev_high = max(highs[-(SMC_SWEEP_LOOKBACK + 5):-SMC_SWEEP_LOOKBACK]) if len(highs) > SMC_SWEEP_LOOKBACK + 5 else recent_high
    prev_low = min(lows[-(SMC_SWEEP_LOOKBACK + 5):-SMC_SWEEP_LOOKBACK]) if len(lows) > SMC_SWEEP_LOOKBACK + 5 else recent_low

    # BOS — Break of Structure
    if closes[-1] > recent_high and highs[-1] > recent_high * SMC_BOS_CONFIRMACAO:
        result["BOS"] = True
        result["ESTRUTURA_OK"] = True
    if closes[-1] < recent_low and lows[-1] < recent_low * (2 - SMC_BOS_CONFIRMACAO):
        result["BOS"] = True
        result["ESTRUTURA_OK"] = True

    # CHOCH — Change of Character
    if recent_high > prev_high and recent_low < prev_low:
        result["CHOCH"] = True

    # LIQUIDITY_SWEEP — varredura acima/abaixo de pivô recente
    for i in range(-SMC_SWEEP_LOOKBACK, -1):
        if len(lows) > abs(i + 1):
            if lows[i] < recent_low and closes[i] > closes[i - 1] and closes[-1] > closes[i]:
                result["LIQUIDITY_SWEEP"] = True
                break

    for i in range(-SMC_SWEEP_LOOKBACK, -1):
        if len(highs) > abs(i + 1):
            if highs[i] > recent_high and closes[i] < closes[i - 1] and closes[-1] < closes[i]:
                result["LIQUIDITY_SWEEP"] = True
                break

    # STOP_HUNT — stop loss caçado
    if result["LIQUIDITY_SWEEP"] and result["BOS"]:
        result["STOP_HUNT"] = True

    # FVG — Fair Value Gap
    for i in range(-10, -1):
        if len(candles) > abs(i + 1):
            gap = min(candles[i][2], candles[i + 1][2]) - max(candles[i][3], candles[i + 1][3])
            if gap > 0:
                result["FVG"] = True
                break

    # ORDER_BLOCK — última vela de tendência antes do movimento
    for i in range(-8, -1):
        if result["BOS"] and closes[-1] > highs[-1]:
            if closes[i] > opens[i] and closes[i + 1] < opens[i + 1]:
                result["ORDER_BLOCK"] = True
                break

    # RETESTE — preço voltou a região do order block ou FVG
    if result.get("ORDER_BLOCK") or result.get("FVG"):
        for i in range(-3, 0):
            if abs(closes[i] - lows[i - 1]) / lows[i - 1] < 0.005:
                result["RETESTE"] = True
                break

    return result
