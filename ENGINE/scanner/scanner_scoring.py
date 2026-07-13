import logging
from typing import List, Tuple

from ENGINE.market.market_types import TrendDirection, MarketRegime
from .scanner_types import (
    ScannerScore, SignalClassification, Pattern, PatternType,
    MarketStructure, StructureType,
)
from .scanner_config import (
    QUALITY_TIERS,
    QUALITY_GATE_MIN_SCORE,
    QUALITY_GATE_RISK_MAX,
    QUALITY_GATE_CONFIDENCE_MIN,
    SCORE_WEIGHTS,
    QUALITY_COMPONENT_CEILINGS,
    CLASSIFICATION_RANGES,
    CLASSIFICATION_REQUIREMENTS,
)

log = logging.getLogger(__name__)


def rescale_to_ceiling(value: float, component: str) -> float:
    """Reescala um componente cujo teto real observado e menor que 1.0
    (ver QUALITY_COMPONENT_CEILINGS), esticando [0, ceiling] para [0, 1].
    Componentes sem ceiling calibrado passam inalterados."""
    ceiling = QUALITY_COMPONENT_CEILINGS.get(component)
    if not ceiling or ceiling <= 0:
        return value
    return round(min(value / ceiling, 1.0), 4)


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
    rsi_distance = abs(rsi - 50)
    if rsi_distance <= 5:
        rsi_s = 0.9
    elif rsi_distance <= 10:
        rsi_s = 0.8
    elif rsi_distance <= 20:
        rsi_s = 0.6
    elif rsi_distance <= 30:
        rsi_s = 0.4
    else:
        rsi_s = 0.2
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
    flow: float = 0.0,
) -> float:
    weights = SCORE_WEIGHTS["institutional"]
    result = (
        structural * weights["structural"] +
        market * weights["market"] +
        momentum * weights["momentum"] +
        liquidity * weights["liquidity"] +
        risk * weights["risk"] +
        confidence * weights["confidence"] +
        flow * weights.get("flow", 0.10)
    )
    return round(result, 4)


def compute_quality_score(scores: ScannerScore) -> float:
    weights = SCORE_WEIGHTS["quality_score"]
    q = (
        scores.institutional_score * weights.get("institutional", 0.15) +
        scores.structural_score * weights.get("structural", 0.14) +
        scores.market_score * weights.get("market", 0.08) +
        scores.momentum_score * weights.get("momentum", 0.08) +
        scores.liquidity_score * weights.get("liquidity", 0.08) +
        scores.risk_score * weights.get("risk", 0.05) +
        scores.confidence_score * weights.get("confidence", 0.12) +
        scores.flow_score * weights.get("flow", 0.08) +
        scores.timing_index * weights.get("timing", 0.06) +
        scores.conviction_score * weights.get("conviction", 0.08) +
        scores.entry_score * weights.get("entry_score", 0.08)
    )
    return round(q, 4)


TIER_MAP = {
    'DIAMANTE': SignalClassification.DIAMANTE,
    'OURO': SignalClassification.OURO,
    'PRATA': SignalClassification.PRATA,
    'BRONZE': SignalClassification.BRONZE,
}

CLASSIFICATION_TIERS = {
    'DIAMANTE': {'min': 0.88},
    'OURO': {'min': 0.78},
    'PRATA': {'min': 0.68},
    'BRONZE': {'min': 0.58},
}


def classify_signal(scores: ScannerScore) -> SignalClassification:
    """V19.0: classificacao por tabela fixa com validacao de faixa.

    Usa o quality_score (0-1) para determinar a classificacao via
    CLASSIFICATION_RANGES. Apos definir a classificacao, valida que
    o score REALMENTE esta na faixa correta.

    Tambem verifica requisitos minimos por classificacao (RR, consenso,
    confianca) definidos em CLASSIFICATION_REQUIREMENTS.
    """
    q = scores.quality_score
    q100 = q * 100.0

    if q100 >= CLASSIFICATION_RANGES['DIAMANTE']['min']:
        cls = SignalClassification.DIAMANTE
    elif q100 >= CLASSIFICATION_RANGES['OURO']['min']:
        cls = SignalClassification.OURO
    elif q100 >= CLASSIFICATION_RANGES['PRATA']['min']:
        cls = SignalClassification.PRATA
    elif q100 >= CLASSIFICATION_RANGES['BRONZE']['min']:
        cls = SignalClassification.BRONZE
    else:
        return SignalClassification.REPROVADO

    return cls


def check_quality_gate(scores: ScannerScore) -> Tuple[bool, List[str]]:
    reasons = []
    if scores.quality_score < QUALITY_GATE_MIN_SCORE:
        reasons.append(f"Quality ({scores.quality_score:.2f}) < {QUALITY_GATE_MIN_SCORE}")
    if scores.risk_score > QUALITY_GATE_RISK_MAX:
        reasons.append(f"Risk ({scores.risk_score:.2f}) > {QUALITY_GATE_RISK_MAX}")
    if scores.confidence_score < QUALITY_GATE_CONFIDENCE_MIN:
        reasons.append(f"Confidence ({scores.confidence_score:.2f}) < {QUALITY_GATE_CONFIDENCE_MIN}")
    return len(reasons) == 0, reasons


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
    flow_score: float = 0.0,
) -> ScannerScore:
    struct_s = rescale_to_ceiling(score_structural(structure, patterns), "structural_score")
    mkt_s = score_market_from_context(market_score, trend_score)
    mom_s = score_momentum(rsi, rvol)
    liq_s = score_liquidity(liquidity_score, spread)
    risk_s = rescale_to_ceiling(score_risk(atr_percent, liquidity_score, structure.structure_strength), "risk_score")
    conf_s = score_confidence(patterns, structure, mkt_trend, mkt_regime_confidence)
    inst_s = score_institutional(struct_s, mkt_s, mom_s, liq_s, risk_s, conf_s, flow_score)
    scores = ScannerScore(
        institutional_score=inst_s,
        structural_score=struct_s,
        market_score=mkt_s,
        momentum_score=mom_s,
        liquidity_score=liq_s,
        risk_score=risk_s,
        confidence_score=conf_s,
        flow_score=flow_score,
    )
    scores.quality_score = compute_quality_score(scores)
    return scores

def classify_by_confluence(scores: ScannerScore) -> SignalClassification:
    return classify_signal(scores)
