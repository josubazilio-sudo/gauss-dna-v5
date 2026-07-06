import logging
import statistics
from typing import List, Tuple

from .market_types import Candle, TechnicalIndicators, TrendDirection
from .market_config import (
    PERIODS_ADX, PERIODS_EMA_9, PERIODS_EMA_21, PERIODS_EMA_50,
    PERIODS_EMA_200, TREND_ADX_THRESHOLD, TREND_ADX_STRONG,
)

log = logging.getLogger(__name__)


def compute_ema(values: List[float], period: int) -> float:
    if len(values) < period:
        return values[-1] if values else 0.0
    multiplier = 2.0 / (period + 1)
    ema = sum(values[:period]) / period
    for v in values[period:]:
        ema = (v - ema) * multiplier + ema
    return ema


def compute_all_emas(candles: List[Candle]) -> Tuple[float, float, float, float]:
    closes = [c.close for c in candles]
    ema_9 = compute_ema(closes, PERIODS_EMA_9) if len(closes) >= PERIODS_EMA_9 else (closes[-1] if closes else 0.0)
    ema_21 = compute_ema(closes, PERIODS_EMA_21) if len(closes) >= PERIODS_EMA_21 else (closes[-1] if closes else 0.0)
    ema_50 = compute_ema(closes, PERIODS_EMA_50) if len(closes) >= PERIODS_EMA_50 else (closes[-1] if closes else 0.0)
    ema_200 = compute_ema(closes, PERIODS_EMA_200) if len(closes) >= PERIODS_EMA_200 else (closes[-1] if closes else 0.0)
    return ema_9, ema_21, ema_50, ema_200


def compute_adx(candles: List[Candle]) -> float:
    if len(candles) < PERIODS_ADX + 1:
        return 0.0
    tr_values = []
    plus_dm_values = []
    minus_dm_values = []
    for i in range(1, len(candles)):
        high = candles[i].high
        low = candles[i].low
        prev_high = candles[i - 1].high
        prev_low = candles[i - 1].low
        prev_close = candles[i - 1].close
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_values.append(tr)
        up_move = high - prev_high
        down_move = prev_low - low
        if up_move > down_move and up_move > 0:
            plus_dm_values.append(up_move)
        else:
            plus_dm_values.append(0.0)
        if down_move > up_move and down_move > 0:
            minus_dm_values.append(down_move)
        else:
            minus_dm_values.append(0.0)
    atr = sum(tr_values[-PERIODS_ADX:]) / PERIODS_ADX
    if atr == 0:
        return 0.0
    avg_plus_dm = sum(plus_dm_values[-PERIODS_ADX:]) / PERIODS_ADX
    avg_minus_dm = sum(minus_dm_values[-PERIODS_ADX:]) / PERIODS_ADX
    plus_di = 100.0 * avg_plus_dm / atr
    minus_di = 100.0 * avg_minus_dm / atr
    di_sum = plus_di + minus_di
    if di_sum == 0:
        return 0.0
    dx = abs(plus_di - minus_di) / di_sum * 100.0
    return dx


def compute_slope(candles: List[Candle], period: int = 10) -> float:
    if len(candles) < period:
        return 0.0
    closes = [c.close for c in candles[-period:]]
    x = list(range(period))
    n = period
    sum_x = sum(x)
    sum_y = sum(closes)
    sum_xy = sum(xi * yi for xi, yi in zip(x, closes))
    sum_x2 = sum(xi * xi for xi in x)
    denom = n * sum_x2 - sum_x * sum_x
    if denom == 0:
        return 0.0
    slope = (n * sum_xy - sum_x * sum_y) / denom
    return slope / (sum(closes) / n) if sum(closes) > 0 else 0.0


def analyze_trend(candles: List[Candle]) -> Tuple[TrendDirection, float]:
    if len(candles) < 20:
        return TrendDirection.NEUTRAL, 0.0
    adx = compute_adx(candles)
    slope = compute_slope(candles, 10)
    ema_9, ema_21, ema_50, ema_200 = compute_all_emas(candles)
    alignments = 0
    if ema_9 > ema_21 > ema_50:
        alignments = 3
    elif ema_9 < ema_21 < ema_50:
        alignments = -3
    elif ema_9 > ema_21:
        alignments = 2
    elif ema_9 < ema_21:
        alignments = -2
    elif ema_9 > ema_50:
        alignments = 1
    elif ema_9 < ema_50:
        alignments = -1
    if ema_200 > 0 and ema_9 > ema_200:
        alignments += 1
    elif ema_200 > 0 and ema_9 < ema_200:
        alignments -= 1

    if slope > 0.001 and alignments >= 2 and adx > TREND_ADX_THRESHOLD:
        direction = TrendDirection.BULLISH
    elif slope < -0.001 and alignments <= -2 and adx > TREND_ADX_THRESHOLD:
        direction = TrendDirection.BEARISH
    else:
        direction = TrendDirection.NEUTRAL

    raw_strength = min(adx / TREND_ADX_STRONG, 1.0)
    alignment_factor = min(abs(alignments) / 3.0, 1.0)
    strength = raw_strength * 0.5 + alignment_factor * 0.5
    return direction, round(strength, 4)
