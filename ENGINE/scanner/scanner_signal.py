import logging
from datetime import datetime, timezone
from typing import List, Tuple, Optional

from .scanner_types import (
    SignalDirection, Signal, ScannerScore, SignalClassification,
    Pattern, MarketStructure, PatternType, StructureType, EntryDetails,
)

log = logging.getLogger(__name__)

_SIGNAL_COUNTER = [0]


def _next_signal_id() -> str:
    _SIGNAL_COUNTER[0] += 1
    return f"SIG-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{_SIGNAL_COUNTER[0]:04d}"


from ENGINE.common.score_normalizer import scale_1_to_100

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
    penalty_reasons: List[str] = None,
    rvol: float = 0.0,
    adx: float = 0.0,
    regime: str = "unknown",
    setup_type: str = "",
    strategy_desc: str = "",
    objective: str = "",
    continuation: str = "",
    tp_multiplier: float = 0.5,
    max_leverage: int = 10,
    volume: float = 0.0,
    explanation: str = "",
    entry_score: float = 0,
    consensus_score: float = 0,
    entry_zone: str = "",
    order_block_distance: float = 0.0,
    fvg_distance: float = 0.0,
    validity: str = "Valido",
    entry_details: Optional["EntryDetails"] = None,
    kalman_direction: str = "UNKNOWN",
    kalman_confidence: float = 0.0,
    kalman_trend_state: str = "ranging",
    kalman_tendency: float = 0.0,
    classification_label: str = "reprovado",
    structure_valid: bool = False,
    false_breakout_clear: bool = False,
    traps_clear: bool = False,
    volume_above_avg: bool = False,
    rvol_confirmed: bool = False,
) -> Signal:
    direction = _resolve_direction(patterns, direction, structure)

    scores.entry_score = entry_score
    scores.consensus_score = consensus_score

    approval_reasons = approval_reasons or []
    if not approval_reasons and classification not in (SignalClassification.REPROVADO,):
        approval_reasons = generate_approval_reasons(patterns, structure, scores, direction, rvol=rvol)
    penalty_reasons = penalty_reasons or []
    if not penalty_reasons and classification not in (SignalClassification.REPROVADO,):
        atr_pct = atr / current_price if current_price > 0 else 0
        penalty_reasons = generate_penalty_reasons(
            scores, atr_percent=atr_pct,
            kalman_confidence=kalman_confidence,
            structure=structure, regime=regime,
        )
    if not explanation and patterns:
        explanation = generate_explanation(patterns, structure, direction, scores, regime)

    setup = _describe_setup(patterns, structure, direction)
    context = _describe_context(scores, classification, direction, penalty_reasons)

    return Signal(
        ticker=ticker,
        timeframe=timeframe,
        direction=direction,
        entry_price=current_price,
        stop_loss=0.0,
        take_profit_1=0.0,
        take_profit_2=0.0,
        risk_reward=0.0,
        scores=scores,
        classification=classification,
        patterns=patterns,
        structure=structure,
        setup=setup,
        context=context,
        approval_reasons=approval_reasons,
        rejection_reasons=rejection_reasons or [],
        penalty_reasons=penalty_reasons,
        confidence=scores.confidence_score,
        quality=scores.quality_score,
        explanation=explanation or "",
        rvol=rvol,
        adx=adx,
        atr_value=atr,
        regime=regime,
        setup_type=setup_type,
        strategy_desc=strategy_desc,
        objective=objective,
        continuation=continuation,
        tp_multiplier=tp_multiplier,
        max_leverage=max_leverage,
        volume=volume,
        ema50=structure.mm50,
        ema200=structure.mm200,
        vwap=structure.vwap,
        structure_strength=structure.structure_strength,
        entry_zone=entry_zone,
        order_block_distance=order_block_distance,
        fvg_distance=fvg_distance,
        validity=validity,
        entry_details=entry_details,
        signal_id=_next_signal_id(),
        kalman_direction=kalman_direction,
        kalman_confidence=kalman_confidence,
        kalman_trend_state=kalman_trend_state,
        kalman_tendency=kalman_tendency,
        classification_label=classification_label,
        structure_valid=structure_valid,
        false_breakout_clear=false_breakout_clear,
        traps_clear=traps_clear,
        volume_above_avg=volume_above_avg,
        rvol_confirmed=rvol_confirmed,
    )


def generate_approval_reasons(
    patterns: List[Pattern],
    structure: MarketStructure,
    scores: ScannerScore,
    direction: SignalDirection,
    rvol: float = 0.0,
    signal: Optional["Signal"] = None,
) -> List[str]:
    reasons = []
    struct_map = {StructureType.UPTREND: "uptrend", StructureType.DOWNTREND: "downtrend", StructureType.RANGING: "ranging"}
    trend_label = struct_map.get(structure.structure_type, "unknown")
    dir_label = "alta" if direction == SignalDirection.LONG else "baixa"
    if structure.structure_type == StructureType.UPTREND and direction == SignalDirection.LONG:
        reasons.append(f"Trend alinhada ({trend_label})")
    elif structure.structure_type == StructureType.DOWNTREND and direction == SignalDirection.SHORT:
        reasons.append(f"Trend alinhada ({trend_label})")
    elif structure.structure_type in (StructureType.UPTREND, StructureType.DOWNTREND):
        reasons.append(f"Contra-trend ({trend_label}, sinal {dir_label})")
    else:
        reasons.append(f"Trend lateral com sinal {dir_label}")

    pattern_names = {
        PatternType.CHOCH: "CHoCH validado",
        PatternType.LIQUIDITY_SWEEP: "Liquidity Sweep",
        PatternType.ORDER_BLOCK: "Order Block confirmado",
        PatternType.BOS: "BOS confirmado",
        PatternType.FVG: "FVG identificado",
    }
    seen = set()
    for p in patterns:
        label = pattern_names.get(p.type)
        if label and label not in seen and p.confidence >= 0.5:
            reasons.append(label)
            seen.add(label)

    if scores.confidence_score >= 0.40:
        reasons.append(f"Confianca {scores.confidence_score:.0%}")
    if scores.structural_score >= 0.40:
        reasons.append(f"Estrutura {scores.structural_score:.0%}")
    if scores.flow_score >= 0.30:
        reasons.append(f"Fluxo institucional {scores.flow_score:.0%}")
    if scores.consensus_score >= 0.40:
        reasons.append(f"Consensus {scores.consensus_score:.0%}")
    if rvol >= 1.0:
        reasons.append("Volume confirmado")
    if scores.liquidity_score >= 0.50:
        reasons.append("Liquidez institucional")
    if scores.quality_score >= 0.40:
        reasons.append(f"Quality {scores.quality_score:.0%}")
    if len(reasons) > 7:
        reasons = reasons[:7]
    if not reasons:
        reasons.append(f"Score geral: {scores.quality_score:.2f}")
    return reasons


def generate_penalty_reasons(
    scores: ScannerScore,
    atr_percent: float = 0.0,
    kalman_confidence: float = 0.0,
    structure: Optional[MarketStructure] = None,
    regime: str = "",
) -> List[str]:
    penalties = []

    if atr_percent > 0.03:
        penalties.append(f"ATR elevado ({atr_percent:.1%})")
    if scores.risk_score > 0.50:
        penalties.append(f"Risco elevado ({scores.risk_score:.0%})")
    if kalman_confidence < 0.30:
        penalties.append("Kalman com baixa confianca")
    if regime and regime.lower() == "ranging":
        penalties.append("Mercado lateral")
    if structure and structure.structure_type == StructureType.RANGING:
        penalties.append("Estrutura indefinida")
    if scores.liquidity_score < 0.40:
        penalties.append("Liquidez abaixo do ideal")
    if scores.momentum_score < 0.30:
        penalties.append("Momentum fraco")

    return penalties[:4]


def generate_explanation(
    patterns: List[Pattern],
    structure: MarketStructure,
    direction: SignalDirection,
    scores: ScannerScore,
    regime: str,
) -> str:
    parts = []
    dir_label = "compra" if direction == SignalDirection.LONG else "venda"
    for p in patterns:
        if p.type == PatternType.CHOCH:
            side = "alta" if p.direction == SignalDirection.LONG else "baixa"
            parts.append(f"CHoCH de {side} detectado")
        elif p.type == PatternType.LIQUIDITY_SWEEP:
            parts.append(f"Liquidity Sweep em {p.price:.2f}")
        elif p.type == PatternType.ORDER_BLOCK:
            side = "compra" if p.direction == SignalDirection.LONG else "venda"
            parts.append(f"Order Block de {side} em {p.price:.2f}")
        elif p.type == PatternType.BOS:
            parts.append(f"BOS confirmado em {p.price:.2f}")
        elif p.type == PatternType.FVG:
            parts.append(f"FVG identificado em {p.price:.2f}")
    if parts:
        summary = " | ".join(parts[:3])
    else:
        summary = f"Sinal de {dir_label} baseado em estrutura de mercado"

    scores_str = (
        f"Quality: {scores.quality_score:.2f} | "
        f"Conviction: {scores.conviction_score:.2f} | "
        f"Flow: {scores.flow_score:.2f} | "
        f"Timing: {scores.timing_index:.2f} | "
        f"Entry: {scores.entry_score:.2f} | "
        f"Consensus: {scores.consensus_score:.2f}"
    )
    ema_context = ""
    if structure.mm50 > 0 and structure.mm200 > 0:
        if structure.mm50 > structure.mm200:
            ema_context = "EMA50 acima da EMA200 (tendencia de alta no medio prazo)"
        else:
            ema_context = "EMA50 abaixo da EMA200 (tendencia de baixa no medio prazo)"
    parts_final = [summary, scores_str]
    if ema_context:
        parts_final.append(ema_context)
    parts_final.append(f"Regime: {regime}")
    if hasattr(scores, 'liquidity_score') and scores.liquidity_score > 0.5:
        parts_final.append("Volume/liquidez favoravel")
    explanation = ". ".join(parts_final)
    return explanation


def _resolve_direction(
    patterns: List[Pattern],
    fallback: SignalDirection,
    structure: Optional[MarketStructure] = None,
) -> SignalDirection:
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

    if structure and structure.structure_type in (StructureType.UPTREND, StructureType.DOWNTREND):
        return SignalDirection.LONG if structure.structure_type == StructureType.UPTREND else SignalDirection.SHORT
    return fallback


def verify_direction_alignment(
    direction: SignalDirection,
    structure: MarketStructure,
    patterns: List[Pattern],
) -> Tuple[bool, List[str]]:
    warnings = []
    if structure.structure_type == StructureType.UPTREND and direction == SignalDirection.SHORT:
        ls_sweeps = [p for p in patterns if p.type == PatternType.LIQUIDITY_SWEEP]
        reversals = [p for p in patterns if p.type in (PatternType.CHOCH,) and p.direction == SignalDirection.SHORT]
        if ls_sweeps or reversals:
            warnings.append("SHORT em UPTREND justificado por Liquidity Sweep/Reversao")
        else:
            warnings.append("SHORT em UPTREND sem confirmacao de reversao")
    elif structure.structure_type == StructureType.DOWNTREND and direction == SignalDirection.LONG:
        ls_sweeps = [p for p in patterns if p.type == PatternType.LIQUIDITY_SWEEP]
        reversals = [p for p in patterns if p.type in (PatternType.CHOCH,) and p.direction == SignalDirection.LONG]
        if ls_sweeps or reversals:
            warnings.append("LONG em DOWNTREND justificado por Liquidity Sweep/Reversao")
        else:
            warnings.append("LONG em DOWNTREND sem confirmacao de reversao")
    else:
        warnings.append(f"Direcao alinhada com estrutura ({structure.structure_type.value})")
    return len([w for w in warnings if "sem confirmacao" in w]) == 0, warnings


def _describe_setup(patterns: List[Pattern], structure: MarketStructure, direction: SignalDirection) -> str:
    parts = [f"Estrutura: {structure.structure_type.value}"]
    if patterns:
        key_patterns = [p for p in patterns if p.type in (
            PatternType.CHOCH, PatternType.LIQUIDITY_SWEEP, PatternType.ORDER_BLOCK,
        )][:3]
        part_desc = "; ".join(p.description for p in key_patterns)
        if part_desc:
            parts.append(f"Padroes: {part_desc}")
    parts.append(f"Direcao: {direction.value}")
    return " | ".join(parts)


def _build_rejected_signal(
    ticker: str,
    timeframe: str,
    direction: SignalDirection,
    patterns: List[Pattern],
    structure: MarketStructure,
    scores: ScannerScore,
    current_price: float,
    regime: str,
    rejection_reason: str,
) -> Signal:
    return Signal(
        ticker=ticker,
        timeframe=timeframe,
        direction=direction,
        entry_price=current_price,
        stop_loss=0.0,
        take_profit_1=0.0,
        take_profit_2=0.0,
        risk_reward=0.0,
        scores=scores,
        classification=SignalClassification.REPROVADO,
        patterns=patterns,
        structure=structure,
        setup="",
        context="",
        approval_reasons=[],
        rejection_reasons=[rejection_reason],
        confidence=0.0,
        quality=0.0,
        regime=regime,
        signal_id=_next_signal_id(),
        classification_label=SignalClassification.REPROVADO.value,
    )


def _describe_context(
    scores: ScannerScore, classification: SignalClassification, direction: SignalDirection,
    penalty_reasons: List[str] = None,
) -> str:
    base = (
        f"Quality: {scores.quality_score:.2f} | "
        f"Institucional: {scores.institutional_score:.2f} | "
        f"Structural: {scores.structural_score:.2f} | "
        f"Risk: {scores.risk_score:.2f} | "
        f"Confidence: {scores.confidence_score:.2f}"
    )
    if penalty_reasons:
        base += " | Penalties: " + "; ".join(penalty_reasons[:2])
    return base
