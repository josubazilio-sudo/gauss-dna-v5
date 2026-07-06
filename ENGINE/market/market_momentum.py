import logging
from typing import List, Tuple

from .market_types import Candle, RsiZone
from .market_config import PERIODS_RSI, RSI_OVERBOUGHT, RSI_OVERSOLD, PERIODS_RVOL

log = logging.getLogger(__name__)


def compute_rsi(candles: List[Candle], period: int = PERIODS_RSI) -> float:
    if len(candles) < period + 1:
        return 50.0
    gains = []
    losses = []
    for i in range(1, len(candles)):
        diff = candles[i].close - candles[i - 1].close
        gains.append(max(diff, 0.0))
        losses.append(max(-diff, 0.0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return round(rsi, 2)


def compute_rvol(candles: List[Candle], period: int = PERIODS_RVOL) -> float:
    if len(candles) < period + 1:
        return 1.0
    current_volume = candles[-1].volume
    volumes = [c.volume for c in candles[-period - 1:-1]]
    avg_volume = sum(volumes) / period if period > 0 else 1.0
    if avg_volume == 0:
        return 1.0
    return round(current_volume / avg_volume, 4)


def compute_avg_volume(candles: List[Candle], period: int = PERIODS_RVOL) -> float:
    if len(candles) < period:
        return sum(c.volume for c in candles) / len(candles) if candles else 0.0
    volumes = [c.volume for c in candles[-period:]]
    return sum(volumes) / period


def classify_rsi(rsi: float) -> RsiZone:
    if rsi >= RSI_OVERBOUGHT:
        return RsiZone.OVERBOUGHT
    if rsi <= RSI_OVERSOLD:
        return RsiZone.OVERSOLD
    return RsiZone.NORMAL


def analyze_momentum(candles: List[Candle]) -> Tuple[float, float, float, float]:
    rsi = compute_rsi(candles)
    rvol = compute_rvol(candles)
    avg_volume = compute_avg_volume(candles)
    volume = candles[-1].volume if candles else 0.0
    return rsi, rvol, avg_volume, volume
