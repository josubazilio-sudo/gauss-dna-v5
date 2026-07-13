import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple

log = logging.getLogger(__name__)


class ResistanceType(Enum):
    SWING_HIGH = "swing_high"
    ORDER_BLOCK = "order_block"
    SUPPLY_ZONE = "supply_zone"
    LIQUIDITY_POOL = "liquidity_pool"
    FVG = "fvg"


@dataclass
class ResistanceLevel:
    rtype: ResistanceType
    price: float
    strength: float
    label: str = ""
    validated_score: float = 0.0


SWING_LOOKBACK = 20
OB_LOOKBACK = 30
FVG_MIN_BODY_PCT = 0.001


def _swing_highs(highs: List[float], lookback: int = SWING_LOOKBACK) -> List[ResistanceLevel]:
    levels = []
    n = len(highs)
    for i in range(1, n - 1):
        if highs[i] > highs[i - 1] and highs[i] > highs[i + 1]:
            left_strength = sum(1 for j in range(max(0, i - lookback), i) if highs[i] > highs[j]) / max(lookback, 1)
            right_strength = sum(1 for j in range(i + 1, min(n, i + lookback + 1)) if highs[i] > highs[j]) / max(lookback, 1)
            strength = (left_strength + right_strength) / 2
            if strength > 0.5:
                levels.append(ResistanceLevel(
                    rtype=ResistanceType.SWING_HIGH,
                    price=highs[i],
                    strength=round(strength, 3),
                    label=f"SwingHigh @ {highs[i]:.4f}",
                ))
    return levels


def _order_blocks(closes: List[float], highs: List[float], lows: List[float],
                  lookback: int = OB_LOOKBACK) -> List[ResistanceLevel]:
    levels = []
    n = len(closes)
    for i in range(2, n):
        prev_body = abs(closes[i - 1] - highs[i - 1] if closes[i - 1] > highs[i - 1] else closes[i - 1] - lows[i - 1])
        body_ratio = abs(closes[i] - closes[i - 1]) / (prev_body + 0.0001)
        if body_ratio > 2.0 and closes[i] > highs[i - 1]:
            strength = min(body_ratio / 5.0, 1.0)
            levels.append(ResistanceLevel(
                rtype=ResistanceType.ORDER_BLOCK,
                price=highs[i - 1],
                strength=round(strength, 3),
                label=f"OB @ {highs[i - 1]:.4f}",
            ))
    return levels


def _supply_zones(closes: List[float], highs: List[float], lows: List[float],
                  lookback: int = 20) -> List[ResistanceLevel]:
    levels = []
    n = len(closes)
    for i in range(3, n):
        if closes[i] < closes[i - 1] and closes[i - 1] < closes[i - 2]:
            if highs[i] > highs[i - 1]:
                zone_high = highs[i]
                zone_low = highs[i - 2]
                retrace = abs(closes[i] - zone_high) / (zone_high - zone_low + 0.0001)
                if retrace > 1.5:
                    strength = min(retrace / 3.0, 1.0)
                    levels.append(ResistanceLevel(
                        rtype=ResistanceType.SUPPLY_ZONE,
                        price=zone_high,
                        strength=round(strength, 3),
                        label=f"Supply @ {zone_high:.4f}",
                    ))
    return levels


def _liquidity_pools(highs: List[float], lows: List[float], lookback: int = 20) -> List[ResistanceLevel]:
    levels = []
    n = len(highs)
    for i in range(1, n - 1):
        if highs[i] > highs[i - 1] and highs[i] > highs[i + 1]:
            left_pool = sum(1 for j in range(max(0, i - lookback), i) if abs(highs[j] - highs[i]) / highs[i] < 0.005)
            right_pool = sum(1 for j in range(i + 1, min(n, i + lookback + 1)) if abs(highs[j] - highs[i]) / highs[i] < 0.005)
            total_pool = left_pool + right_pool
            if total_pool >= 3:
                strength = min(total_pool / 10.0, 1.0)
                levels.append(ResistanceLevel(
                    rtype=ResistanceType.LIQUIDITY_POOL,
                    price=highs[i],
                    strength=round(strength, 3),
                    label=f"Liquidity @ {highs[i]:.4f}",
                ))
    return levels


def _fvgs(closes: List[float], highs: List[float], lows: List[float]) -> List[ResistanceLevel]:
    levels = []
    n = len(closes)
    for i in range(2, n):
        if lows[i] > highs[i - 2]:
            gap = lows[i] - highs[i - 2]
            avg_price = (closes[i] + closes[i - 2]) / 2
            gap_pct = gap / avg_price if avg_price > 0 else 0
            if gap_pct >= FVG_MIN_BODY_PCT:
                strength = min(gap_pct * 100, 1.0)
                levels.append(ResistanceLevel(
                    rtype=ResistanceType.FVG,
                    price=lows[i],
                    strength=round(strength, 3),
                    label=f"FVG @ {lows[i]:.4f}",
                ))
    return levels


def scan_resistance(
    highs: List[float],
    lows: List[float],
    closes: List[float],
    include_types: List[ResistanceType] = None,
) -> List[ResistanceLevel]:
    if include_types is None:
        include_types = list(ResistanceType)
    levels: List[ResistanceLevel] = []
    mapper = {
        ResistanceType.SWING_HIGH: _swing_highs(highs),
        ResistanceType.ORDER_BLOCK: _order_blocks(closes, highs, lows),
        ResistanceType.SUPPLY_ZONE: _supply_zones(closes, highs, lows),
        ResistanceType.LIQUIDITY_POOL: _liquidity_pools(highs, lows),
        ResistanceType.FVG: _fvgs(closes, highs, lows),
    }
    for rt in include_types:
        levels.extend(mapper.get(rt, []))
    levels.sort(key=lambda x: x.price)
    for lv in levels:
        lv.validated_score = compute_validated_score(lv, highs, lows, closes, levels)
    log.debug("ResistanceScanner: found %d levels (%d types)", len(levels), len(include_types))
    return levels


def find_nearest_resistance_above(
    price: float,
    levels: List[ResistanceLevel],
    min_strength: float = 0.3,
) -> Optional[ResistanceLevel]:
    strong = [l for l in levels if l.strength >= min_strength and l.price > price]
    if not strong:
        return None
    return min(strong, key=lambda l: l.price - price)


def find_nearest_resistance_below(
    price: float,
    levels: List[ResistanceLevel],
    min_strength: float = 0.3,
) -> Optional[ResistanceLevel]:
    strong = [l for l in levels if l.strength >= min_strength and l.price < price]
    if not strong:
        return None
    return max(strong, key=lambda l: price - l.price)


def compute_validated_score(
    level: ResistanceLevel,
    highs: List[float],
    lows: List[float],
    closes: List[float],
    all_levels: List[ResistanceLevel] = None,
) -> float:
    price = level.price
    tolerance = price * 0.003
    touch_count = sum(1 for h in highs if abs(h - price) / price < 0.002)
    touch_count = max(touch_count - 1, 0)
    touch_score = min(touch_count * 10, 30)

    strength_score = level.strength * 35

    type_bonus = {
        ResistanceType.ORDER_BLOCK: 15,
        ResistanceType.LIQUIDITY_POOL: 12,
        ResistanceType.SWING_HIGH: 10,
        ResistanceType.SUPPLY_ZONE: 8,
        ResistanceType.FVG: 5,
    }.get(level.rtype, 5)

    fvg_alignment = 0
    if level.rtype != ResistanceType.FVG and len(closes) > 2:
        for i in range(2, len(closes)):
            if lows[i] > highs[i - 2]:
                gap_low, gap_high = highs[i - 2], lows[i]
                if gap_low <= price <= gap_high:
                    fvg_alignment = 10
                    break

    multi_type = 0
    if all_levels:
        nearby = [l for l in all_levels if l is not level and abs(l.price - price) / price < 0.01]
        types_nearby = len(set(l.rtype for l in nearby))
        multi_type = min(types_nearby * 5, 10)

    score = touch_score + strength_score + type_bonus + fvg_alignment + multi_type
    return round(min(score, 100.0), 1)


def strongest_resistance_in_range(
    price: float,
    levels: List[ResistanceLevel],
    range_pct: float = 0.02,
) -> Optional[ResistanceLevel]:
    half = price * range_pct
    candidates = [l for l in levels if abs(l.price - price) / price <= range_pct]
    if not candidates:
        return None
    return max(candidates, key=lambda l: l.strength)
