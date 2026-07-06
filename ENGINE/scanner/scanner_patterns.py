import logging
from typing import List, Tuple

from ENGINE.market.market_types import Candle
from .scanner_types import Pattern, PatternType, SignalDirection, SwingPoint
from .scanner_config import (
    SWING_LOOKBACK, SWING_LEFT_RIGHT, BOS_CONFIRMATION_BARS,
    FVG_MIN_GAP_BPS, OB_CONFIRMATION_BARS, LIQUIDITY_SWEEP_RETRACE,
)

log = logging.getLogger(__name__)


def find_swing_points(candles: List[Candle], lookback: int = SWING_LOOKBACK) -> List[SwingPoint]:
    if len(candles) < lookback * 2 + 1:
        return []
    swings = []
    for i in range(lookback, len(candles) - lookback):
        is_high = True
        is_low = True
        for j in range(i - lookback, i + lookback + 1):
            if j == i:
                continue
            if candles[j].high >= candles[i].high:
                is_high = False
            if candles[j].low <= candles[i].low:
                is_low = False
        if is_high:
            swings.append(SwingPoint(price=candles[i].high, index=i, high=True))
        if is_low:
            swings.append(SwingPoint(price=candles[i].low, index=i, high=False))
    return swings


def detect_bos(candles: List[Candle], swings: List[SwingPoint], tf: str) -> List[Pattern]:
    patterns = []
    if len(swings) < 3:
        return patterns
    recent_highs = [s for s in swings if s.high][-5:]
    recent_lows = [s for s in swings if not s.high][-5:]
    if len(recent_highs) >= 2:
        last = recent_highs[-1]
        prev = recent_highs[-2]
        if last.price > prev.price and last.index > prev.index:
            last_candles = candles[-BOS_CONFIRMATION_BARS:]
            if all(c.close > prev.price for c in last_candles):
                patterns.append(Pattern(
                    type=PatternType.BOS,
                    direction=SignalDirection.LONG,
                    timeframe=tf,
                    price=last.price,
                    confidence=0.65,
                    strength=min((last.price - prev.price) / prev.price * 100, 1.0),
                    description=f"BOS acima de {prev.price:.2f}",
                    metadata={"prev_high": prev.price, "new_high": last.price},
                ))
    if len(recent_lows) >= 2:
        last = recent_lows[-1]
        prev = recent_lows[-2]
        if last.price < prev.price and last.index > prev.index:
            last_candles = candles[-BOS_CONFIRMATION_BARS:]
            if all(c.close < prev.price for c in last_candles):
                patterns.append(Pattern(
                    type=PatternType.BOS,
                    direction=SignalDirection.SHORT,
                    timeframe=tf,
                    price=last.price,
                    confidence=0.65,
                    strength=min((prev.price - last.price) / prev.price * 100, 1.0),
                    description=f"BOS abaixo de {prev.price:.2f}",
                    metadata={"prev_low": prev.price, "new_low": last.price},
                ))
    return patterns


def detect_choch(candles: List[Candle], swings: List[SwingPoint], tf: str) -> List[Pattern]:
    patterns = []
    if len(swings) < 4:
        return patterns
    recent = swings[-4:]
    if not recent:
        return patterns
    last_two_highs = [s for s in recent if s.high][-2:]
    last_two_lows = [s for s in recent if not s.high][-2:]
    if len(last_two_highs) >= 2 and len(last_two_lows) >= 2:
        h1, h2 = last_two_highs[-2], last_two_highs[-1]
        l1, l2 = last_two_lows[-2], last_two_lows[-1]
        if h1.price > h2.price and l1.price > l2.price and h1.index < l2.index:
            patterns.append(Pattern(
                type=PatternType.CHOCH,
                direction=SignalDirection.SHORT,
                timeframe=tf,
                price=l2.price,
                confidence=0.80,
                strength=min((h1.price - l2.price) / h1.price * 100, 1.0),
                description=f"CHoCH baixa: lower high + lower low",
                metadata={"prev_high": h1.price, "new_low": l2.price},
            ))
        if h1.price < h2.price and l1.price < l2.price and l1.index < h2.index:
            patterns.append(Pattern(
                type=PatternType.CHOCH,
                direction=SignalDirection.LONG,
                timeframe=tf,
                price=h2.price,
                confidence=0.80,
                strength=min((h2.price - l1.price) / l1.price * 100, 1.0),
                description=f"CHoCH alta: higher high + higher low",
                metadata={"prev_low": l1.price, "new_high": h2.price},
            ))
    return patterns


def detect_order_blocks(candles: List[Candle], tf: str) -> List[Pattern]:
    patterns = []
    if len(candles) < 5:
        return patterns
    for i in range(2, len(candles) - 2):
        prev = candles[i - 1]
        curr = candles[i]
        next_ = candles[i + 1]
        body_curr = abs(curr.close - curr.open)
        body_prev = abs(prev.close - prev.open)
        if body_curr == 0 or body_prev == 0:
            continue
        bullish_move = next_.close > curr.high and body_curr > body_prev * 1.5
        if bullish_move and curr.close < curr.open:
            patterns.append(Pattern(
                type=PatternType.ORDER_BLOCK,
                direction=SignalDirection.LONG,
                timeframe=tf,
                price=curr.high,
                confidence=0.75,
                strength=min(body_curr / body_prev, 3.0) / 3.0,
                description=f"Order Block bullish em {curr.high:.2f}",
                metadata={"index": i, "body_ratio": body_curr / body_prev if body_prev > 0 else 1.0},
            ))
        bearish_move = next_.close < curr.low and body_curr > body_prev * 1.5
        if bearish_move and curr.close > curr.open:
            patterns.append(Pattern(
                type=PatternType.ORDER_BLOCK,
                direction=SignalDirection.SHORT,
                timeframe=tf,
                price=curr.low,
                confidence=0.75,
                strength=min(body_curr / body_prev, 3.0) / 3.0,
                description=f"Order Block bearish em {curr.low:.2f}",
                metadata={"index": i, "body_ratio": body_curr / body_prev if body_prev > 0 else 1.0},
            ))
    return patterns


def detect_fvg(candles: List[Candle], tf: str) -> List[Pattern]:
    patterns = []
    if len(candles) < 3:
        return patterns
    for i in range(1, len(candles) - 1):
        prev = candles[i - 1]
        curr = candles[i]
        nxt = candles[i + 1]
        if prev.low > nxt.high:
            gap_bps = ((prev.low - nxt.high) / nxt.high) * 10000
            if gap_bps >= FVG_MIN_GAP_BPS:
                patterns.append(Pattern(
                    type=PatternType.FVG,
                    direction=SignalDirection.LONG,
                    timeframe=tf,
                    price=(prev.low + nxt.high) / 2,
                    confidence=0.70,
                    strength=min(gap_bps / 50, 1.0),
                    description=f"FVG bullish: {nxt.high:.2f} - {prev.low:.2f} ({gap_bps:.1f}bps)",
                    metadata={"gap_top": prev.low, "gap_bottom": nxt.high, "gap_bps": gap_bps},
                ))
        if prev.high < nxt.low:
            gap_bps = ((nxt.low - prev.high) / prev.high) * 10000
            if gap_bps >= FVG_MIN_GAP_BPS:
                patterns.append(Pattern(
                    type=PatternType.FVG,
                    direction=SignalDirection.SHORT,
                    timeframe=tf,
                    price=(prev.high + nxt.low) / 2,
                    confidence=0.70,
                    strength=min(gap_bps / 50, 1.0),
                    description=f"FVG bearish: {prev.high:.2f} - {nxt.low:.2f} ({gap_bps:.1f}bps)",
                    metadata={"gap_top": prev.high, "gap_bottom": nxt.low, "gap_bps": gap_bps},
                ))
    return patterns


def detect_liquidity_sweeps(candles: List[Candle], swings: List[SwingPoint], tf: str) -> List[Pattern]:
    patterns = []
    if len(swings) < 3 or len(candles) < 20:
        return patterns
    last_swings = swings[-4:]
    highs = [s for s in last_swings if s.high]
    lows = [s for s in last_swings if not s.high]
    recent = candles[-10:]
    for h in highs[-2:]:
        sweep_high = any(c.high > h.price for c in recent)
        if sweep_high and recent[-1].close < h.price:
            retrace = (max(c.high for c in recent) - h.price) / h.price
            if retrace < 0.02:
                patterns.append(Pattern(
                    type=PatternType.LIQUIDITY_SWEEP,
                    direction=SignalDirection.SHORT,
                    timeframe=tf,
                    price=h.price,
                    confidence=0.80,
                    strength=min(retrace * 100, 1.0),
                    description=f"Liquidity sweep em high {h.price:.2f}",
                    metadata={"swept_price": h.price, "high_swept": max(c.high for c in recent)},
                ))
    for l in lows[-2:]:
        sweep_low = any(c.low < l.price for c in recent)
        if sweep_low and recent[-1].close > l.price:
            retrace = (l.price - min(c.low for c in recent)) / l.price
            if retrace < 0.02:
                patterns.append(Pattern(
                    type=PatternType.LIQUIDITY_SWEEP,
                    direction=SignalDirection.LONG,
                    timeframe=tf,
                    price=l.price,
                    confidence=0.80,
                    strength=min(retrace * 100, 1.0),
                    description=f"Liquidity sweep em low {l.price:.2f}",
                    metadata={"swept_price": l.price, "low_swept": min(c.low for c in recent)},
                ))
    return patterns


def scan_all_patterns(candles: List[Candle], tf: str) -> List[Pattern]:
    swings = find_swing_points(candles)
    patterns = []
    patterns.extend(detect_bos(candles, swings, tf))
    patterns.extend(detect_choch(candles, swings, tf))
    patterns.extend(detect_order_blocks(candles, tf))
    patterns.extend(detect_fvg(candles, tf))
    patterns.extend(detect_liquidity_sweeps(candles, swings, tf))
    return patterns
