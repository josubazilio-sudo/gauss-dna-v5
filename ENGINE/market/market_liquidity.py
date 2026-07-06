import logging
from typing import Tuple

from .market_config import (
    LIQUIDITY_SPREAD_GOOD, LIQUIDITY_SPREAD_ACCEPTABLE,
    LIQUIDITY_SPREAD_POOR, LIQUIDITY_FUNDING_WARN, LIQUIDITY_FUNDING_CRITICAL,
)

log = logging.getLogger(__name__)


def score_spread(spread: float) -> float:
    if spread <= LIQUIDITY_SPREAD_GOOD:
        return 1.0
    if spread <= LIQUIDITY_SPREAD_ACCEPTABLE:
        return 0.7
    if spread <= LIQUIDITY_SPREAD_POOR:
        return 0.4
    return 0.1


def score_funding(funding_rate: float) -> float:
    abs_funding = abs(funding_rate)
    if abs_funding <= LIQUIDITY_FUNDING_WARN / 2:
        return 1.0
    if abs_funding <= LIQUIDITY_FUNDING_WARN:
        return 0.8
    if abs_funding <= LIQUIDITY_FUNDING_CRITICAL:
        return 0.5
    return 0.2


def score_volume_quality(rvol: float, avg_volume: float) -> float:
    if avg_volume <= 0:
        return 0.3
    if rvol >= 2.0:
        return 1.0
    if rvol >= 1.5:
        return 0.9
    if rvol >= 1.0:
        return 0.8
    if rvol >= 0.5:
        return 0.6
    return 0.4


def analyze_liquidity(
    spread: float, funding_rate: float, rvol: float, avg_volume: float,
) -> Tuple[float, float, float]:
    spread_s = score_spread(spread)
    funding_s = score_funding(funding_rate)
    volume_s = score_volume_quality(rvol, avg_volume)
    composite = spread_s * 0.4 + funding_s * 0.3 + volume_s * 0.3
    return round(composite, 4), spread_s, funding_s
