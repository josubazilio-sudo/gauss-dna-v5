import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from ENGINE.risk.resistance_scanner import (
    ResistanceLevel, ResistanceType, scan_resistance,
    find_nearest_resistance_above, find_nearest_resistance_below,
)
from ENGINE.scanner.scanner_config import RR_MIN_RR

log = logging.getLogger(__name__)

ATR_MULT_TP1 = 1.8
PARTIAL_GAIN_PCT = 0.02
PARTIAL_ATR_MULT = 1.0
TRAILING_ATR_MULT = 1.5
TRAILING_EMA_PERIOD = 21
DIFFICULTY_HIGH_THRESHOLD = 70
TP_PROBABILITY_MIN = 75.0
RESISTANCE_SCORE_MIN = 75.0


@dataclass
class TPResult:
    tp1: float = 0.0
    tp2: float = 0.0
    partial_tp: float = 0.0
    break_even_price: float = 0.0
    tp_probability: float = 0.0
    target_difficulty: float = 0.0
    resistance_used: str = ""
    trailing_active: bool = False
    trailing_start_price: float = 0.0


def _ema(values: List[float], period: int) -> Optional[float]:
    if len(values) < period:
        return None
    k = 2.0 / (period + 1)
    ema = sum(values[-period:]) / period
    for v in values[-(period - 1):]:
        ema = v * k + ema * (1 - k)
    return ema


def calculate_tp_probability(
    trend_score: float = 0.5,
    momentum: float = 0.5,
    adx: float = 25.0,
    volume_ratio: float = 1.0,
    distance_to_resistance_pct: float = 0.0,
    atr_pct: float = 0.0,
) -> float:
    adx_norm = min(adx / 50.0, 1.0)
    vol_norm = min(volume_ratio / 2.0, 1.0)
    dist_norm = max(1.0 - distance_to_resistance_pct * 100, 0.0)

    prob = (
        trend_score * 0.25
        + momentum * 0.20
        + adx_norm * 0.20
        + vol_norm * 0.15
        + dist_norm * 0.20
    )
    return round(min(prob * 100, 100.0), 1)


def calculate_target_difficulty(
    atr_pct: float,
    distance_to_resistance_pct: float,
    trend_strength: float = 0.5,
    volatility_ratio: float = 1.0,
) -> float:
    atr_score = min(atr_pct * 500, 50)
    dist_score = min(distance_to_resistance_pct * 200, 30)
    trend_penalty = (1.0 - trend_strength) * 15
    vol_penalty = min(volatility_ratio * 10, 20)
    difficulty = atr_score + dist_score + trend_penalty + vol_penalty
    return round(min(difficulty, 100.0), 1)


def calculate_adaptive_tp(
    entry: float,
    stop_loss: float,
    direction: str,
    atr: float,
    closes: List[float],
    highs: List[float],
    lows: List[float],
    trend_score: float = 0.5,
    momentum: float = 0.5,
    adx: float = 25.0,
    volume_ratio: float = 1.0,
    trend_strength: float = 0.5,
    volatility_ratio: float = 1.0,
) -> TPResult:
    result = TPResult()
    is_long = direction.upper() in ("LONG", "BUY")

    atr_price = atr
    atr_pct = atr / entry if entry > 0 else 0

    resistance_levels = scan_resistance(highs, lows, closes)
    nearest_res = (find_nearest_resistance_above(entry, resistance_levels)
                   if is_long else find_nearest_resistance_below(entry, resistance_levels))

    distance_to_res_pct = 0.0
    if nearest_res:
        distance_to_res_pct = abs(nearest_res.price - entry) / entry

    tp_atr = entry + atr_price * ATR_MULT_TP1 if is_long else entry - atr_price * ATR_MULT_TP1

    tp_final = tp_atr
    result.resistance_used = ""
    if nearest_res:
        validated_ok = nearest_res.validated_score >= RESISTANCE_SCORE_MIN
        tp_res = nearest_res.price * 0.999 if is_long else nearest_res.price * 1.001
        if (is_long and tp_res < tp_atr) or (not is_long and tp_res > tp_atr):
            if validated_ok:
                tp_final = tp_res
                result.resistance_used = f"{nearest_res.rtype.value} @ {nearest_res.price:.4f} (score={nearest_res.validated_score:.0f})"
            else:
                log.info(
                    "TPAdaptativo: resistance %s @ %.4f ignored (score=%.1f < %.0f)",
                    nearest_res.rtype.value, nearest_res.price,
                    nearest_res.validated_score, RESISTANCE_SCORE_MIN,
                )

    result.tp_probability = calculate_tp_probability(
        trend_score, momentum, adx, volume_ratio,
        distance_to_res_pct, atr_pct,
    )

    if result.tp_probability < TP_PROBABILITY_MIN:
        reduction = 1.0 - (TP_PROBABILITY_MIN - result.tp_probability) / 200.0
        reduction = max(reduction, 0.85)
        if is_long:
            tp_final = entry + (tp_final - entry) * reduction
        else:
            tp_final = entry - (entry - tp_final) * reduction

    result.target_difficulty = calculate_target_difficulty(
        atr_pct, distance_to_res_pct, trend_strength, volatility_ratio,
    )

    if result.target_difficulty > DIFFICULTY_HIGH_THRESHOLD:
        if is_long:
            tp_final = entry + (tp_final - entry) * 0.85
        else:
            tp_final = entry - (entry - tp_final) * 0.85

    risk = abs(entry - stop_loss) if stop_loss != entry else atr_price
    tp2_risk_mult = 3.0
    if is_long:
        tp2 = entry + risk * tp2_risk_mult
    else:
        tp2 = entry - risk * tp2_risk_mult

    if (is_long and tp2 <= tp_final) or (not is_long and tp2 >= tp_final):
        tp2 = tp_final + (atr_price * 0.5) if is_long else tp_final - (atr_price * 0.5)

    partial_price = entry * (1 + PARTIAL_GAIN_PCT) if is_long else entry * (1 - PARTIAL_GAIN_PCT)
    partial_atr_price = entry + atr_price * PARTIAL_ATR_MULT if is_long else entry - atr_price * PARTIAL_ATR_MULT
    if (is_long and partial_atr_price < partial_price) or (not is_long and partial_atr_price > partial_price):
        partial_price = partial_atr_price

    prec = max(2, 8 - int(entry // 1))

    rr = abs(tp_final - entry) / abs(stop_loss - entry) if abs(stop_loss - entry) > 0 else 0
    if rr < RR_MIN_RR:
        risk = abs(stop_loss - entry)
        tp_final = entry + risk * RR_MIN_RR if is_long else entry - risk * RR_MIN_RR
        log.info(
            "TPAdaptativo: RR %.2f < RR_MIN_RR %.1f, ajustando tp1 -> %.4f",
            rr, RR_MIN_RR, tp_final,
        )

    result.tp1 = round(tp_final, prec)
    result.tp2 = round(tp2, prec)
    result.partial_tp = round(partial_price, prec)
    result.break_even_price = round(entry, prec)
    result.trailing_active = False
    result.trailing_start_price = 0.0

    log.info(
        "TPAdaptativo: entry=%.4f sl=%.4f dir=%s tp1=%.4f tp2=%.4f "
        "partial=%.4f prob=%.1f%% difficulty=%.1f resistance=%s",
        entry, stop_loss, direction,
        result.tp1, result.tp2,
        result.partial_tp,
        result.tp_probability, result.target_difficulty,
        result.resistance_used or "none",
    )

    return result


def should_take_partial(
    current_price: float,
    entry_price: float,
    direction: str,
    atr: float,
    partial_tp: float,
) -> Tuple[bool, str]:
    is_long = direction.upper() in ("LONG", "BUY")
    if is_long and current_price >= partial_tp:
        return True, "partial_gain"
    if not is_long and current_price <= partial_tp:
        return True, "partial_gain"
    gain_pct = abs(current_price - entry_price) / entry_price if entry_price > 0 else 0
    if gain_pct >= PARTIAL_GAIN_PCT:
        return True, "partial_pct"
    atr_gain = abs(current_price - entry_price)
    if atr_gain >= atr * PARTIAL_ATR_MULT:
        return True, "partial_atr"
    return False, ""


def should_activate_trailing(
    current_price: float,
    entry_price: float,
    direction: str,
    tp1: float,
) -> bool:
    is_long = direction.upper() in ("LONG", "BUY")
    if is_long and current_price >= tp1:
        return True
    if not is_long and current_price <= tp1:
        return True
    return False


def calculate_trailing_stop(
    current_price: float,
    entry_price: float,
    direction: str,
    atr: float,
    closes: List[float],
) -> Optional[float]:
    is_long = direction.upper() in ("LONG", "BUY")
    ema_val = _ema(closes, TRAILING_EMA_PERIOD)
    atr_dist = atr * TRAILING_ATR_MULT

    if is_long:
        trail_price = current_price - atr_dist
        if ema_val is not None:
            trail_price = max(trail_price, ema_val)
        return max(trail_price, entry_price)
    else:
        trail_price = current_price + atr_dist
        if ema_val is not None:
            trail_price = min(trail_price, ema_val)
        return min(trail_price, entry_price)
