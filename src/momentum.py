"""Módulo 5: Momentum — preenche variáveis MOMENTUM."""

from config import RSI_PERIOD, RSI_LONG_MIN, RSI_LONG_MAX, RSI_SHORT_MIN, RSI_SHORT_MAX, ADX_PERIOD, ATR_PERIOD, MACD_FAST, MACD_SLOW, MACD_SIGNAL


def analyze_momentum(candles):
    """
    Preenche RSI, RSI_LONG, RSI_SHORT, ADX, ATR,
    ATR_MEDIO, MOMENTUM, HEIKIN_ASHI, HA_BULL, HA_BEAR.
    """
    result = {
        "RSI": 50.0,
        "RSI_LONG": False,
        "RSI_SHORT": False,
        "ADX": 0.0,
        "ADX_MINIMO": 20,
        "ATR": 0.0,
        "ATR_MEDIO": 0.0,
        "MOMENTUM": "neutro",
        "HEIKIN_ASHI": "neutra",
        "HA_BULL": False,
        "HA_BEAR": False,
        "MACD": None,
        "MACD_SIGNAL": None,
        "MACD_HIST": None,
        "MACD_BULLISH": False,
        "MACD_BEARISH": False,
        "MACD_HIST_CRESCENTE": False,
    }

    closes = [c[4] for c in candles]
    highs = [c[2] for c in candles]
    lows = [c[3] for c in candles]

    if len(closes) < 20:
        return result

    result["RSI"] = _calc_rsi(closes, RSI_PERIOD)
    result["RSI_LONG"] = RSI_LONG_MIN <= result["RSI"] <= RSI_LONG_MAX
    result["RSI_SHORT"] = RSI_SHORT_MIN <= result["RSI"] <= RSI_SHORT_MAX

    result["ADX"] = _calc_adx(highs, lows, closes, ADX_PERIOD)
    result["ATR"] = _calc_atr(highs, lows, closes, ATR_PERIOD)
    result["ATR_MEDIO"] = result["ATR"]

    result["MOMENTUM"] = "crescente" if closes[-1] > closes[-10] else "decrescente"

    ha = _calc_heikin_ashi(candles)
    result["HEIKIN_ASHI"] = ha
    result["HA_BULL"] = ha == "alta"
    result["HA_BEAR"] = ha == "baixa"

    macd, signal, hist = _calc_macd(closes)
    result["MACD"] = macd
    result["MACD_SIGNAL"] = signal
    result["MACD_HIST"] = hist
    if macd is not None and signal is not None:
        if len(closes) >= MACD_SLOW + MACD_SIGNAL + 2:
            prev_macd, prev_signal, _ = _calc_macd(closes[:-1])
            result["MACD_BULLISH"] = prev_macd <= prev_signal and macd > signal
            result["MACD_BEARISH"] = prev_macd >= prev_signal and macd < signal
        if hist is not None and len(closes) >= MACD_SLOW + MACD_SIGNAL + 3:
            _, _, hist_prev = _calc_macd(closes[:-2])
            if hist_prev is not None:
                result["MACD_HIST_CRESCENTE"] = hist > hist_prev

    return result


def _calc_rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50
    gains, losses = [], []
    for i in range(1, period + 1):
        diff = closes[-i] - closes[-i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _calc_adx(highs, lows, closes, period=14):
    if len(highs) < period * 2:
        return 15
    tr_list, plus_dm, minus_dm = [], [], []
    for i in range(1, len(closes)):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        tr_list.append(tr)
        up_move = highs[i] - highs[i - 1]
        down_move = lows[i - 1] - lows[i]
        plus_dm.append(up_move if up_move > down_move and up_move > 0 else 0)
        minus_dm.append(down_move if down_move > up_move and down_move > 0 else 0)
    atr = sum(tr_list[-period:]) / period
    apd = sum(plus_dm[-period:]) / period
    amd = sum(minus_dm[-period:]) / period
    pdi = (apd / atr) * 100 if atr > 0 else 0
    mdi = (amd / atr) * 100 if atr > 0 else 0
    dx = abs(pdi - mdi) / (pdi + mdi) * 100 if (pdi + mdi) > 0 else 0
    return dx


def _calc_atr(highs, lows, closes, period=14):
    if len(highs) < period + 1:
        return 0
    tr = []
    for i in range(1, period + 1):
        tr.append(max(highs[-i] - lows[-i], abs(highs[-i] - closes[-i - 1]), abs(lows[-i] - closes[-i - 1])))
    return sum(tr) / period


def _calc_macd(closes, fast=None, slow=None, signal=None):
    fast = fast or MACD_FAST
    slow = slow or MACD_SLOW
    signal_period = signal or MACD_SIGNAL
    if len(closes) < slow + signal_period:
        return None, None, None
    def ema(data, period):
        k = 2 / (period + 1)
        result = [sum(data[:period]) / period]
        for price in data[period:]:
            result.append(price * k + result[-1] * (1 - k))
        return result
    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    macd_line = [ema_fast[i] - ema_slow[i] for i in range(len(ema_slow))]
    signal_line = ema(macd_line, signal_period)
    macd_val = macd_line[-1]
    signal_val = signal_line[-1]
    hist = macd_val - signal_val
    return macd_val, signal_val, hist


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
