import logging
import statistics
from typing import List, Tuple

from .market_types import Candle, VolatilityZone
from .market_config import (
    PERIODS_ATR, PERIODS_BB, BB_STD_MULTIPLIER,
    VOLATILITY_ATR_LOW, VOLATILITY_ATR_MODERATE,
    VOLATILITY_ATR_HIGH,
)

log = logging.getLogger(__name__)


def compute_atr(candles: List[Candle], period: int = PERIODS_ATR) -> float:
    if len(candles) < period + 1:
        return 0.0
    tr_values = []
    for i in range(1, len(candles)):
        high = candles[i].high
        low = candles[i].low
        prev_close = candles[i - 1].close
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_values.append(tr)
    if not tr_values:
        return 0.0
    return sum(tr_values[-period:]) / period


def compute_bollinger_bands(
    candles: List[Candle], period: int = PERIODS_BB, std_mult: float = BB_STD_MULTIPLIER,
) -> Tuple[float, float, float]:
    if len(candles) < period:
        last = candles[-1].close if candles else 0.0
        return last, last, last
    closes = [c.close for c in candles[-period:]]
    mean = sum(closes) / period
    variance = sum((c - mean) ** 2 for c in closes) / period
    std = variance ** 0.5
    upper = mean + std_mult * std
    lower = mean - std_mult * std
    return mean, upper, lower


def bb_position(close: float, upper: float, lower: float, middle: float) -> float:
    if upper == lower:
        return 0.5
    return (close - lower) / (upper - lower)


def classify_volatility(atr_percent: float) -> VolatilityZone:
    if atr_percent < VOLATILITY_ATR_LOW:
        return VolatilityZone.LOW
    if atr_percent < VOLATILITY_ATR_MODERATE:
        return VolatilityZone.MODERATE
    if atr_percent < VOLATILITY_ATR_HIGH:
        return VolatilityZone.HIGH
    return VolatilityZone.EXTREME


def analyze_volatility(candles: List[Candle]) -> Tuple[float, float, float, float, float, float, float]:
    atr = compute_atr(candles)
    close = candles[-1].close if candles else 1.0
    atr_percent = atr / close if close > 0 else 0.0
    bb_mid, bb_upper, bb_lower = compute_bollinger_bands(candles)
    bb_w = (bb_upper - bb_lower) / bb_mid if bb_mid > 0 else 0.0
    bb_pos = bb_position(close, bb_upper, bb_lower, bb_mid)
    return atr, atr_percent, bb_mid, bb_upper, bb_lower, bb_w, bb_pos
