import logging
from typing import Tuple

from .market_types import TrendDirection, MarketRegime
from .market_config import TREND_ADX_THRESHOLD

log = logging.getLogger(__name__)


def classify_regime(
    trend: TrendDirection,
    trend_strength: float,
    adx: float,
    atr_percent: float,
    rsi: float,
    bb_width: float,
    rvol: float,
) -> Tuple[MarketRegime, float]:
    is_high_vol = atr_percent > 0.02 or bb_width > 0.08
    is_low_vol = atr_percent < 0.003 and bb_width < 0.02
    is_trending = adx > TREND_ADX_THRESHOLD and trend_strength > 0.5
    is_ranging = adx < 20 and not is_high_vol and not is_low_vol
    is_reversal_rsi = (rsi <= 30 or rsi >= 70) and trend_strength > 0.6

    if is_low_vol and not is_trending:
        confidence = 0.5
        return MarketRegime.CALM, round(confidence, 4)

    if is_reversal_rsi and is_high_vol:
        confidence = 0.7 if abs(rsi - 50) > 25 else 0.5
        return MarketRegime.REVERSAL, round(confidence, 4)

    if is_high_vol and not is_trending:
        confidence = min(atr_percent / 0.03, 1.0)
        return MarketRegime.VOLATILE, round(confidence, 4)

    if trend == TrendDirection.BULLISH and is_trending:
        confidence = 0.5 + trend_strength * 0.4
        return MarketRegime.TRENDING_UP, round(min(confidence, 1.0), 4)

    if trend == TrendDirection.BEARISH and is_trending:
        confidence = 0.5 + trend_strength * 0.4
        return MarketRegime.TRENDING_DOWN, round(min(confidence, 1.0), 4)

    if is_ranging:
        confidence = 0.6
        return MarketRegime.RANGING, round(confidence, 4)

    return MarketRegime.RANGING, 0.3
