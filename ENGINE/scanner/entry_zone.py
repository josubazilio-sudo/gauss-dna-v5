import logging
from typing import List, Optional, Tuple
from .scanner_types import Pattern, PatternType, EntryZone, EntryDetails, SignalDirection
from .scanner_config import ENTRY_ZONE_MAX_AGE, ENTRY_ZONE_MAX_ATR_DISTANCE, ENTRY_ZONE_SCORE_MIN

log = logging.getLogger(__name__)


def _is_mitigated(pattern: Pattern, current_price: float) -> bool:
    if pattern.type == PatternType.ORDER_BLOCK:
        low = pattern.metadata.get('lower', 0)
        high = pattern.metadata.get('upper', 0)
        if pattern.direction == SignalDirection.LONG:
            return current_price < low
        else:
            return current_price > high

    if pattern.type == PatternType.FVG:
        lower = pattern.metadata.get('lower', 0)
        upper = pattern.metadata.get('upper', 0)
        return lower <= current_price <= upper

    return False


def _zone_age(pattern: Pattern, max_candles: int) -> bool:
    idx = pattern.metadata.get('index', -1)
    if idx < 0:
        return True
    return idx > max_candles


def _distance_to_zone(pattern: Pattern, current_price: float) -> float:
    upper = pattern.metadata.get('upper', pattern.price)
    lower = pattern.metadata.get('lower', pattern.price)
    ideal = (upper + lower) / 2
    return abs(current_price - ideal)


def _entry_score(distance: float, atr: float) -> float:
    if atr <= 0:
        return 0.0
    max_dist = atr * ENTRY_ZONE_MAX_ATR_DISTANCE
    if max_dist <= 0:
        return 0.0
    return max(0.0, 1.0 - (distance / max_dist))


def _rank_pattern(
    pattern: Pattern,
    current_price: float,
    atr: float,
    all_patterns: List[Pattern],
) -> Tuple[float, str]:
    scores = []
    weight_sum = 0

    dist = _distance_to_zone(pattern, current_price)
    max_dist = atr * ENTRY_ZONE_MAX_ATR_DISTANCE if atr > 0 else dist + 1
    dist_score = max(0.0, 1.0 - (dist / max_dist))
    scores.append(("distancia", dist_score, 0.30))
    weight_sum += 0.30

    mit_score = 0.0 if _is_mitigated(pattern, current_price) else 1.0
    scores.append(("mitigacao", mit_score, 0.15))
    weight_sum += 0.15

    conf_score = pattern.confidence
    scores.append(("confianca", conf_score, 0.15))
    weight_sum += 0.15

    str_score = pattern.strength
    scores.append(("forca", str_score, 0.10))
    weight_sum += 0.10

    pat_idx = pattern.metadata.get("index", -1)
    other_bos = any(
        p.type == PatternType.BOS
        and p.direction == pattern.direction
        and abs(p.metadata.get("index", -1) - pat_idx) <= 10
        for p in all_patterns
    )
    bos_score = 1.0 if other_bos else 0.0
    scores.append(("bos", bos_score, 0.10))
    weight_sum += 0.10

    other_choch = any(
        p.type == PatternType.CHOCH
        and p.direction == pattern.direction
        and abs(p.metadata.get("index", -1) - pat_idx) <= 10
        for p in all_patterns
    )
    choch_score = 1.0 if other_choch else 0.0
    scores.append(("choch", choch_score, 0.10))
    weight_sum += 0.10

    other_sweep = any(
        p.type == PatternType.LIQUIDITY_SWEEP
        and abs(p.metadata.get("index", -1) - pat_idx) <= 10
        for p in all_patterns
    )
    sweep_score = 1.0 if other_sweep else 0.0
    scores.append(("sweep", sweep_score, 0.05))
    weight_sum += 0.05

    other_fvg = any(
        p.type == PatternType.FVG
        and p.direction == pattern.direction
        and abs(p.metadata.get("index", -1) - pat_idx) <= 10
        for p in all_patterns
    ) if pattern.type == PatternType.ORDER_BLOCK else any(
        p.type == PatternType.ORDER_BLOCK
        and p.direction == pattern.direction
        and abs(p.metadata.get("index", -1) - pat_idx) <= 10
        for p in all_patterns
    )
    fvg_score = 1.0 if other_fvg else 0.0
    scores.append(("fvg_assoc", fvg_score, 0.05))
    weight_sum += 0.05

    total = sum(s * w for _, s, w in scores)
    if weight_sum > 0:
        total = total / weight_sum

    details = "; ".join(f"{k}={v:.2f}" for k, v, _ in scores)
    return total, details


def calculate_entry_zone(
    patterns: List[Pattern],
    current_price: float,
    atr: float,
    candles: Optional[List] = None,
    direction: Optional[SignalDirection] = None,
) -> EntryDetails:
    zone_candidates = [
        p for p in patterns
        if p.type in (PatternType.ORDER_BLOCK, PatternType.FVG)
        and (direction is None or p.direction == direction)
    ]

    if not zone_candidates:
        return EntryDetails(EntryZone(0, 0, 0, 0, 'none'), 0.0, False)

    total_candles = len(candles) if candles else 0
    valid = []
    for p in zone_candidates:
        if _is_mitigated(p, current_price):
            continue
        if total_candles > 0 and not _zone_age(p, total_candles - ENTRY_ZONE_MAX_AGE):
            continue
        dist = _distance_to_zone(p, current_price)
        if atr > 0 and dist > atr * ENTRY_ZONE_MAX_ATR_DISTANCE:
            continue
        valid.append(p)

    if not valid:
        fallback = zone_candidates[0]
        atr_safe = atr if atr > 0 else abs(current_price) * 0.005
        upper = fallback.metadata.get('upper', fallback.price + (atr_safe * 0.5))
        lower = fallback.metadata.get('lower', fallback.price - (atr_safe * 0.5))
        ideal = (upper + lower) / 2
        dist = abs(current_price - ideal)
        score = _entry_score(dist, atr_safe)
        status = 'inside' if lower <= current_price <= upper else ('above' if current_price > upper else 'below')
        zone = EntryZone(upper, lower, ideal, score, status)
        return EntryDetails(zone, score, False)

    ranked = []
    for p in valid:
        rank_score, details = _rank_pattern(p, current_price, atr, patterns)
        ranked.append((rank_score, details, p))

    ranked.sort(key=lambda x: x[0], reverse=True)

    best_score, best_details, best = ranked[0]
    dist = _distance_to_zone(best, current_price)
    upper = best.metadata.get('upper', best.price + (atr * 0.5))
    lower = best.metadata.get('lower', best.price - (atr * 0.5))
    ideal = (upper + lower) / 2
    score = _entry_score(dist, atr)
    status = 'inside' if lower <= current_price <= upper else ('above' if current_price > upper else 'below')
    score_approved = score >= ENTRY_ZONE_SCORE_MIN

    zone = EntryZone(upper, lower, ideal, score, status)
    return EntryDetails(zone, score, score_approved, approved=score_approved)


# backward compat — codigo legado importa ENTRY_SCORE_MIN (percentual)
ENTRY_SCORE_MIN = int(ENTRY_ZONE_SCORE_MIN * 100)  # 45
