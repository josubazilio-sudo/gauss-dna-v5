"""Módulo 5: Momentum (RSI, ADX, ATR, Heikin Ashi)."""


def ema(data, period):
    if len(data) < period:
        return None
    k = 2 / (period + 1)
    result = [sum(data[:period]) / period]
    for val in data[period:]:
        result.append(val * k + result[-1] * (1 - k))
    return result


def analyze_momentum(candles):
    """
    Analisa RSI, ADX, ATR e Heikin Ashi.
    """
    result = {
        "rsi": 50,
        "adx": 15,
        "atr": 0,
        "ha_tendencia": "neutra",
        "momentum_crescente": False,
        "momentum_decrescente": False,
    }

    closes = [c[4] for c in candles]
    highs = [c[2] for c in candles]
    lows = [c[3] for c in candles]

    result["rsi"] = _calc_rsi(closes, 14)
    result["adx"] = _calc_adx(highs, lows, closes, 14)
    result["atr"] = _calc_atr_single(highs, lows, closes)
    result["ha_tendencia"] = _calc_heikin_ashi(candles)
    result["momentum_crescente"] = closes[-1] > closes[-10] if len(closes) > 10 else False
    result["momentum_decrescente"] = closes[-1] < closes[-10] if len(closes) > 10 else False

    return result


def _calc_rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50
    gains = []
    losses = []
    for i in range(1, period + 1):
        diff = closes[-i] - closes[-i - 1]
        if diff >= 0:
            gains.append(diff)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(diff))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _calc_adx(highs, lows, closes, period=14):
    if len(highs) < period * 2:
        return 15
    tr_list = []
    plus_dm = []
    minus_dm = []
    for i in range(1, len(closes)):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        tr_list.append(tr)
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]
        if up_move > down_move and up_move > 0:
            plus_dm.append(up_move)
        else:
            plus_dm.append(0)
        if down_move > up_move and down_move > 0:
            minus_dm.append(down_move)
        else:
            minus_dm.append(0)
    atr = sum(tr_list[-period:]) / period
    apd = sum(plus_dm[-period:]) / period
    amd = sum(minus_dm[-period:]) / period
    pdi = (apd / atr) * 100 if atr > 0 else 0
    mdi = (amd / atr) * 100 if atr > 0 else 0
    dx = abs(pdi - mdi) / (pdi + mdi) * 100 if (pdi + mdi) > 0 else 0
    return dx


def _calc_atr_single(highs, lows, closes, period=14):
    if len(highs) < period + 1:
        return 0
    tr = []
    for i in range(1, period + 1):
        tr.append(max(highs[-i] - lows[-i], abs(highs[-i] - closes[-i - 1]), abs(lows[-i] - closes[-i - 1])))
    return sum(tr) / period


def _calc_heikin_ashi(candles):
    if len(candles) < 3:
        return "neutra"
    ha_closes = []
    for i in range(len(candles)):
        ha_c = (candles[i][1] + candles[i][2] + candles[i][3] + candles[i][4]) / 4
        ha_closes.append(ha_c)
    if ha_closes[-1] > ha_closes[-3] and ha_closes[-1] > ha_closes[-2]:
        return "alta"
    if ha_closes[-1] < ha_closes[-3] and ha_closes[-1] < ha_closes[-2]:
        return "baixa"
    return "neutra"
