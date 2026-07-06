import logging
from typing import List

from ENGINE.market.market_types import Candle
from .scanner_types import (
    MarketStructure, StructureType, SwingPoint,
    Pattern, PatternType, SignalDirection,
)
from .scanner_patterns import find_swing_points
from .scanner_config import SWING_LOOKBACK

log = logging.getLogger(__name__)


def analyze_structure(candles: List[Candle]) -> MarketStructure:
    swings = find_swing_points(candles, SWING_LOOKBACK)
    closes = [c.close for c in candles]
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]

    mm50 = _moving_average(closes, 50)
    mm200 = _moving_average(closes, 200)
    vwap_val = _vwap(candles)

    recent_highs = [s for s in swings if s.high][-5:]
    recent_lows = [s for s in swings if not s.high][-5:]

    st = StructureType.RANGING
    strength = 0.0
    last_break = None

    if len(recent_highs) >= 3 and len(recent_lows) >= 3:
        highs_up = all(
            recent_highs[i].price > recent_highs[i - 1].price
            for i in range(1, len(recent_highs))
        )
        lows_up = all(
            recent_lows[i].price > recent_lows[i - 1].price
            for i in range(1, len(recent_lows))
        )
        highs_down = all(
            recent_highs[i].price < recent_highs[i - 1].price
            for i in range(1, len(recent_highs))
        )
        lows_down = all(
            recent_lows[i].price < recent_lows[i - 1].price
            for i in range(1, len(recent_lows))
        )

        if highs_up and lows_up:
            st = StructureType.UPTREND
            strength = _calc_strength(recent_highs, recent_lows, True)
            last_break = "hh_hl"
        elif highs_down and lows_down:
            st = StructureType.DOWNTREND
            strength = _calc_strength(recent_highs, recent_lows, False)
            last_break = "lh_ll"
        else:
            last_high = recent_highs[-1].price if recent_highs else 0
            prev_high = recent_highs[-2].price if len(recent_highs) >= 2 else 0
            last_low = recent_lows[-1].price if recent_lows else 0
            prev_low = recent_lows[-2].price if len(recent_lows) >= 2 else 0
            if last_high > prev_high and last_low > prev_low:
                st = StructureType.UPTREND
                strength = 0.4
            elif last_high < prev_high and last_low < prev_low:
                st = StructureType.DOWNTREND
                strength = 0.4
            elif last_high > prev_high and last_low < prev_low:
                st = StructureType.REVERSAL
                strength = 0.5
                last_break = "divergence"

    current_price = closes[-1] if closes else 0.0
    mm50_dist = (current_price - mm50) / mm50 if mm50 > 0 else 0.0
    mm200_dist = (current_price - mm200) / mm200 if mm200 > 0 else 0.0
    vwap_dist = (current_price - vwap_val) / vwap_val if vwap_val > 0 else 0.0

    mm50_t = "above" if mm50_dist > 0 else "below"
    mm200_t = "above" if mm200_dist > 0 else "below"

    return MarketStructure(
        structure_type=st,
        swing_highs=recent_highs,
        swing_lows=recent_lows,
        last_break=last_break,
        structure_strength=round(strength, 4),
        mm50=round(mm50, 4),
        mm200=round(mm200, 4),
        vwap=round(vwap_val, 4),
        vwap_distance=round(vwap_dist, 6),
        mm50_distance=round(mm50_dist, 6),
        mm200_distance=round(mm200_dist, 6),
        mm50_trend=mm50_t,
        mm200_trend=mm200_t,
    )


def _moving_average(values: List[float], period: int) -> float:
    if len(values) < period:
        return values[-1] if values else 0.0
    return sum(values[-period:]) / period


def _vwap(candles: List[Candle]) -> float:
    if not candles:
        return 0.0
    total_pv = sum((c.high + c.low + c.close) / 3 * c.volume for c in candles)
    total_vol = sum(c.volume for c in candles)
    return total_pv / total_vol if total_vol > 0 else 0.0


def _calc_strength(highs: List[SwingPoint], lows: List[SwingPoint], bullish: bool) -> float:
    if len(highs) < 2 or len(lows) < 2:
        return 0.0
    if bullish:
        h_gain = (highs[-1].price - highs[0].price) / highs[0].price
        l_gain = (lows[-1].price - lows[0].price) / lows[0].price
    else:
        h_gain = (highs[0].price - highs[-1].price) / highs[0].price
        l_gain = (lows[0].price - lows[-1].price) / lows[0].price
    return min((h_gain + l_gain) / 2 * 10, 1.0)
