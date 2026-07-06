import logging
from typing import List, Tuple

from .scanner_types import (
    SignalDirection, Signal, ScannerScore, SignalClassification,
    Pattern, MarketStructure, PatternType,
)

log = logging.getLogger(__name__)


def build_signal(
    ticker: str,
    timeframe: str,
    direction: SignalDirection,
    patterns: List[Pattern],
    structure: MarketStructure,
    scores: ScannerScore,
    classification: SignalClassification,
    current_price: float,
    funding_rate: float = 0.0,
    atr: float = 0.0,
    approval_reasons: List[str] = None,
    rejection_reasons: List[str] = None,
) -> Signal:
    direction = _resolve_direction(patterns, direction)
    entry_price, stop_loss, take_profit_1, take_profit_2 = _calculate_levels(
        current_price, direction, atr, structure,
    )
    risk_reward = _calculate_rr(entry_price, stop_loss, take_profit_1, direction)

    setup = _describe_setup(patterns, structure, direction)
    context = _describe_context(scores, classification, direction)

    return Signal(
        ticker=ticker,
        timeframe=timeframe,
        direction=direction,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit_1=take_profit_1,
        take_profit_2=take_profit_2,
        risk_reward=round(risk_reward, 2),
        scores=scores,
        classification=classification,
        patterns=patterns,
        structure=structure,
        setup=setup,
        context=context,
        approval_reasons=approval_reasons or [],
        rejection_reasons=rejection_reasons or [],
        confidence=scores.confidence_score,
        quality=scores.quality_score,
    )


def _resolve_direction(patterns: List[Pattern], fallback: SignalDirection) -> SignalDirection:
    longs = sum(1 for p in patterns if p.direction == SignalDirection.LONG)
    shorts = sum(1 for p in patterns if p.direction == SignalDirection.SHORT)
    if longs > shorts:
        return SignalDirection.LONG
    if shorts > longs:
        return SignalDirection.SHORT
    choch = [p for p in patterns if p.type == PatternType.CHOCH]
    if choch:
        return choch[0].direction
    liquidity = [p for p in patterns if p.type == PatternType.LIQUIDITY_SWEEP]
    if liquidity:
        return liquidity[0].direction
    return fallback


def _calculate_levels(
    price: float, direction: SignalDirection, atr: float, structure: MarketStructure,
) -> Tuple[float, float, float, float]:
    atr = atr if atr > 0 else price * 0.005
    if direction == SignalDirection.LONG:
        entry = price
        sl = price - atr * 1.5
        tp1 = price + atr * 2.0
        tp2 = price + atr * 3.5
    elif direction == SignalDirection.SHORT:
        entry = price
        sl = price + atr * 1.5
        tp1 = price - atr * 2.0
        tp2 = price - atr * 3.5
    else:
        return price, price * 0.99, price * 1.01, price * 1.02
    sl = max(sl, price * 0.9) if direction == SignalDirection.LONG else min(sl, price * 1.1)
    tp1 = min(tp1, price * 1.1) if direction == SignalDirection.LONG else max(tp1, price * 0.9)
    tp2 = min(tp2, price * 1.2) if direction == SignalDirection.LONG else max(tp2, price * 0.8)
    return round(entry, 4), round(sl, 4), round(tp1, 4), round(tp2, 4)


def _calculate_rr(entry: float, sl: float, tp1: float, direction: SignalDirection) -> float:
    if direction == SignalDirection.LONG:
        risk = entry - sl
        reward = tp1 - entry
    else:
        risk = sl - entry
        reward = entry - tp1
    if risk <= 0:
        return 0.0
    return reward / risk


def _describe_setup(patterns: List[Pattern], structure: MarketStructure, direction: SignalDirection) -> str:
    parts = [f"Estrutura: {structure.structure_type.value}"]
    if patterns:
        key_patterns = [p for p in patterns if p.type in (
            PatternType.CHOCH, PatternType.LIQUIDITY_SWEEP, PatternType.ORDER_BLOCK,
        )][:3]
        part_desc = "; ".join(p.description for p in key_patterns)
        if part_desc:
            parts.append(f"Padrões: {part_desc}")
    parts.append(f"Direção: {direction.value}")
    return " | ".join(parts)


def _describe_context(
    scores: ScannerScore, classification: SignalClassification, direction: SignalDirection,
) -> str:
    return (
        f"Quality: {scores.quality_score:.2f} | "
        f"Institucional: {scores.institutional_score:.2f} | "
        f"Structural: {scores.structural_score:.2f} | "
        f"Risk: {scores.risk_score:.2f} | "
        f"Confidence: {scores.confidence_score:.2f}"
    )
