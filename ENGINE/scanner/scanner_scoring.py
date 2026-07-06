import logging
from typing import List, Tuple

from ENGINE.market.market_types import TrendDirection, MarketRegime
from .scanner_types import (
    ScannerScore, SignalClassification, Pattern, PatternType,
    MarketStructure, StructureType,
)
from .scanner_config import (
    SCORE_THRESHOLD_OURO_SUPREMO, SCORE_THRESHOLD_OURO,
    SCORE_THRESHOLD_PRATA, SCORE_THRESHOLD_BRONZE, SCORE_THRESHOLD_MINIMUM,
    SCORE_WEIGHTS, QUALITY_GATE_RISK_MAX,
)

log = logging.getLogger(__name__)


def score_structural(structure: MarketStructure, patterns: List[Pattern]) -> float:
    base = structure.structure_strength
    num_patterns = min(len(patterns) / 3, 1.0) * 0.3
    confidence_sum = sum(p.confidence for p in patterns) / max(len(patterns), 1)
    conf_factor = confidence_sum * 0.2
    result = base * 0.5 + num_patterns * 0.3 + conf_factor * 0.2
    return round(min(result, 1.0), 4)


def score_market_from_context(market_score: float, trend_score: float) -> float:
    return round((market_score * 0.6 + trend_score * 0.4), 4)


def score_momentum(rsi: float, rvol: float) -> float:
    rvol_s = min(rvol / 2.0, 1.0) * 0.4
    rsi_s = 0.3 + (abs(rsi - 50) / 50.0) * 0.4
    return round(min(rsi_s * 0.6 + rvol_s, 1.0), 4)


def score_liquidity(liquidity_score: float, spread: float) -> float:
    spread_penalty = min(spread / 0.005, 1.0) * 0.3
    return round(max(liquidity_score * 0.7 + (1.0 - spread_penalty) * 0.3, 0.0), 4)


def score_risk(atr_percent: float, liquidity_score: float, structure_strength: float) -> float:
    vol_risk = 1.0 - min(atr_percent / 0.025, 1.0)
    liq_factor = liquidity_score * 0.3
    str_factor = structure_strength * 0.2
    result = vol_risk * 0.5 + liq_factor * 0.3 + str_factor * 0.2
    return round(min(result, 1.0), 4)


def score_confidence(
    patterns: List[Pattern], structure: MarketStructure,
    mkt_trend: TrendDirection, mkt_regime_confidence: float,
) -> float:
    if not patterns:
        return 0.2
    avg_confidence = sum(p.confidence for p in patterns) / len(patterns)
    pattern_diversity = min(len(set(p.type.value for p in patterns)) / 3, 1.0)
    struct_align = 0.5
    if structure.structure_type == StructureType.UPTREND and any(
        p.direction.value == "long" for p in patterns
    ):
        struct_align = 0.8
    elif structure.structure_type == StructureType.DOWNTREND and any(
        p.direction.value == "short" for p in patterns
    ):
        struct_align = 0.8
    regime_conf = mkt_regime_confidence * 0.2
    result = avg_confidence * 0.4 + pattern_diversity * 0.2 + struct_align * 0.25 + regime_conf
    return round(min(result, 1.0), 4)


def score_institutional(
    structural: float, market: float, momentum: float,
    liquidity: float, risk: float, confidence: float,
) -> float:
    weights = SCORE_WEIGHTS["quality_score"]
    result = (
        structural * weights["structural"] +
        market * weights["market"] +
        momentum * weights["momentum"] +
        liquidity * weights["liquidity"] +
        risk * weights["risk"] +
        confidence * weights["confidence"]
    )
    return round(result, 4)


def compute_quality_score(scores: ScannerScore) -> float:
    weights = SCORE_WEIGHTS["quality_score"]
    q = (
        scores.institutional_score * weights["institutional"] +
        scores.structural_score * weights["structural"] +
        scores.market_score * weights["market"] +
        scores.momentum_score * weights["momentum"] +
        scores.liquidity_score * weights["liquidity"] +
        scores.risk_score * weights["risk"] +
        scores.confidence_score * weights["confidence"]
    )
    return round(q, 4)


def classify_signal(scores: ScannerScore) -> SignalClassification:
    q = scores.quality_score
    if q >= SCORE_THRESHOLD_OURO_SUPREMO:
        return SignalClassification.OURO_SUPREMO
    if q >= SCORE_THRESHOLD_OURO:
        return SignalClassification.OURO
    if q >= SCORE_THRESHOLD_PRATA:
        return SignalClassification.PRATA
    if q >= SCORE_THRESHOLD_BRONZE:
        return SignalClassification.BRONZE
    return SignalClassification.REPROVADO


def check_quality_gate(scores: ScannerScore) -> Tuple[bool, List[str]]:
    reasons = []
    if scores.quality_score < SCORE_THRESHOLD_PRATA:
        reasons.append(f"Quality Score ({scores.quality_score:.2f}) abaixo do mínimo (0.60)")
    if scores.market_score < 0.40:
        reasons.append(f"Market Score ({scores.market_score:.2f}) insuficiente")
    if scores.risk_score > QUALITY_GATE_RISK_MAX:
        reasons.append(f"Risk Score ({scores.risk_score:.2f}) elevado")
    if scores.confidence_score < 0.40:
        reasons.append(f"Confidence Score ({scores.confidence_score:.2f}) baixo")
    passed = len(reasons) == 0
    return passed, reasons


def compute_all_scanner_scores(
    structure: MarketStructure,
    patterns: List[Pattern],
    market_score: float,
    trend_score: float,
    rsi: float,
    rvol: float,
    atr_percent: float,
    liquidity_score: float,
    spread: float,
    mkt_trend: TrendDirection,
    mkt_regime_confidence: float,
) -> ScannerScore:
    struct_s = score_structural(structure, patterns)
    mkt_s = score_market_from_context(market_score, trend_score)
    mom_s = score_momentum(rsi, rvol)
    liq_s = score_liquidity(liquidity_score, spread)
    risk_s = score_risk(atr_percent, liquidity_score, structure.structure_strength)
    conf_s = score_confidence(patterns, structure, mkt_trend, mkt_regime_confidence)
    inst_s = score_institutional(struct_s, mkt_s, mom_s, liq_s, risk_s, conf_s)
    scores = ScannerScore(
        institutional_score=inst_s,
        structural_score=struct_s,
        market_score=mkt_s,
        momentum_score=mom_s,
        liquidity_score=liq_s,
        risk_score=risk_s,
        confidence_score=conf_s,
    )
    scores.quality_score = compute_quality_score(scores)
    return scores
