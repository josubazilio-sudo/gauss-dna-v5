from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


SSR_WEIGHTS = {
    "quality": 0.25,
    "confidence": 0.15,
    "consensus": 0.15,
    "entry_score": 0.15,
    "institutional": 0.10,
    "structural": 0.08,
    "liquidity": 0.07,
    "market": 0.05,
}


SSR_TIERS = [
    (95, "INSTITUCIONAL", "\u2b50\u2b50\u2b50\u2b50\u2b50"),
    (85, "ELITE", "\u2b50\u2b50\u2b50\u2b50\u2606"),
    (75, "ALTA QUALIDADE", "\u2b50\u2b50\u2b50\u2606\u2606"),
    (65, "OPORTUNIDADE", "\u2b50\u2b50\u2606\u2606\u2606"),
]


def _to_100(v: float) -> float:
    return v * 100.0 if v <= 1.0 else v


def compute_ssr(
    quality: float = 0.0,
    confidence: float = 0.0,
    consensus: float = 0.0,
    entry_score: float = 0.0,
    institutional: float = 0.0,
    structural: float = 0.0,
    liquidity: float = 0.0,
    market: float = 0.0,
    weights: Optional[Dict[str, float]] = None,
) -> float:
    w = weights or SSR_WEIGHTS
    q = _to_100(quality) * w["quality"]
    c = _to_100(confidence) * w["confidence"]
    cs = _to_100(consensus) * w["consensus"]
    e = _to_100(entry_score) * w["entry_score"]
    i = _to_100(institutional) * w["institutional"]
    s = _to_100(structural) * w["structural"]
    l = _to_100(liquidity) * w["liquidity"]
    m = _to_100(market) * w["market"]
    total = q + c + cs + e + i + s + l + m
    return round(min(100.0, max(0.0, total)), 1)


def ssr_from_scores(
    quality_score: float,
    confidence_score: float,
    consensus_score: float,
    entry_score: float,
    institutional_score: float,
    structural_score: float,
    liquidity_score: float,
    market_score: float,
) -> float:
    return compute_ssr(
        quality=quality_score,
        confidence=confidence_score,
        consensus=consensus_score,
        entry_score=entry_score,
        institutional=institutional_score,
        structural=structural_score,
        liquidity=liquidity_score,
        market=market_score,
    )


def classify_ssr(ssr: float) -> Tuple[str, str]:
    for threshold, name, stars in SSR_TIERS:
        if ssr >= threshold:
            return name, stars
    return "OBSERVACAO", "\u2b50\u2606\u2606\u2606\u2606"


def ssr_alert(ssr: float) -> Optional[str]:
    if ssr > 95:
        return "\U0001f6a8 PRIORIDADE MAXIMA"
    if ssr > 90:
        return "\U0001f525 SINAL PREMIUM"
    return None
