import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .world_config import (
    CONFIDENCE_MINIMUM,
    CORRELATION_HIGH,
    DOMINANCE_BTC_HIGH,
    DOMINANCE_ETH_HIGH,
    FUNDING_NEGATIVE,
    FUNDING_POSITIVE,
    HEALTH_MINIMUM,
    LIQUIDITY_HIGH,
    LIQUIDITY_LOW,
    QUALITY_MINIMUM,
    TREND_STRONG_THRESHOLD,
    TREND_WEAK_THRESHOLD,
    VOLATILITY_HIGH,
    VOLATILITY_LOW,
    WORLD_MODEL_VERSION,
)
from .world_types import MarketQuality, MarketState, WorldModel

log = logging.getLogger(__name__)


def _infer_state(
    adx: float,
    trend_strength: float,
    volatility_score: float,
    regime: str,
) -> MarketState:
    strong_trend = trend_strength >= TREND_STRONG_THRESHOLD
    weak_trend = trend_strength <= TREND_WEAK_THRESHOLD
    high_vol = volatility_score >= VOLATILITY_HIGH
    low_vol = volatility_score <= VOLATILITY_LOW

    if regime == "trending_up" and strong_trend and adx >= 30:
        return MarketState.STRONG_TREND_UP
    if regime == "trending_down" and strong_trend and adx >= 30:
        return MarketState.STRONG_TREND_DOWN
    if regime == "trending_up":
        return MarketState.WEAK_TREND_UP
    if regime == "trending_down":
        return MarketState.WEAK_TREND_DOWN
    if regime == "ranging":
        if high_vol:
            return MarketState.EXPANSION
        if low_vol:
            return MarketState.COMPRESSION
        return MarketState.RANGING
    if regime == "volatile":
        return MarketState.HIGH_VOLATILITY
    if regime == "calm":
        return MarketState.LOW_VOLATILITY
    if regime == "reversal":
        return MarketState.DISTRIBUTION

    return MarketState.UNCERTAIN


def _infer_quality(
    confidence: float,
    volatility_score: float,
    liquidity_score: float,
    regime_confidence: float,
) -> MarketQuality:
    if (
        confidence >= 0.80
        and liquidity_score >= LIQUIDITY_HIGH
        and regime_confidence >= 0.70
        and 0.005 <= volatility_score <= 0.03
    ):
        return MarketQuality.EXCELLENT
    if (
        confidence >= 0.60
        and liquidity_score >= LIQUIDITY_LOW
        and regime_confidence >= 0.50
        and volatility_score <= 0.05
    ):
        return MarketQuality.GOOD
    if (
        confidence >= 0.40
        and liquidity_score >= 0.20
        and volatility_score <= 0.08
    ):
        return MarketQuality.FAIR
    if (
        volatility_score >= 0.08
        or liquidity_score <= 0.10
        or confidence <= 0.20
    ):
        return MarketQuality.HOSTILE
    return MarketQuality.POOR


def _infer_volatility_label(volatility_score: float) -> str:
    if volatility_score >= VOLATILITY_HIGH:
        return "high"
    if volatility_score <= VOLATILITY_LOW:
        return "low"
    return "moderate"


def _infer_liquidity_label(liquidity_score: float) -> str:
    if liquidity_score >= LIQUIDITY_HIGH:
        return "high"
    if liquidity_score <= LIQUIDITY_LOW:
        return "low"
    return "normal"


def evaluate_global_trend(
    adx: float,
    trend_strength: float,
    regime: str,
) -> str:
    if trend_strength >= TREND_STRONG_THRESHOLD and adx >= 25:
        if regime in ("trending_up",):
            return "bullish"
        if regime in ("trending_down",):
            return "bearish"
    if trend_strength >= TREND_WEAK_THRESHOLD:
        if "up" in regime:
            return "slightly_bullish"
        if "down" in regime:
            return "slightly_bearish"
    return "neutral"


def build_world_model(
    market_context: Any,
    skill_health: Optional[Dict[str, float]] = None,
    active_skills: Optional[List[str]] = None,
) -> WorldModel:
    indicators = getattr(market_context, "indicators", None)
    adx = getattr(indicators, "adx", 0.0) if indicators else 0.0
    rvol = getattr(indicators, "rvol", 0.0) if indicators else 0.0
    rsi = getattr(indicators, "rsi", 50.0) if indicators else 50.0
    atr_pct = getattr(indicators, "atr_percent", 0.0) if indicators else 0.0

    trend_strength = getattr(market_context, "trend_strength", 0.0)
    regime = getattr(market_context, "regime", None)
    regime_str = regime.value if hasattr(regime, "value") else str(regime or "unknown")
    regime_confidence = getattr(market_context, "regime_confidence", 0.0)

    volatility_score = getattr(market_context, "volatility_score", 0.0)
    liquidity_score = getattr(market_context, "liquidity_score", 0.0)
    correlation = getattr(market_context, "btc_correlation", 0.0)
    btc_dom = getattr(market_context, "btc_dominance", 0.0)
    funding = getattr(market_context, "funding_rate", 0.0)
    oi = getattr(market_context, "open_interest", None)
    confidence = getattr(market_context, "confidence_score", 0.0)
    eth_dom = getattr(market_context, "eth_dominance", 0.0)

    inferred_state = _infer_state(adx, trend_strength, volatility_score, regime_str)
    quality = _infer_quality(confidence, volatility_score, liquidity_score, regime_confidence)

    global_trend = evaluate_global_trend(adx, trend_strength, regime_str)

    return WorldModel(
        version=WORLD_MODEL_VERSION,
        timestamp=datetime.now(timezone.utc),
        state=inferred_state,
        quality=quality,
        global_trend=global_trend,
        local_trend=global_trend,
        trend_strength=trend_strength,
        volatility=_infer_volatility_label(volatility_score),
        volatility_score=volatility_score,
        liquidity=_infer_liquidity_label(liquidity_score),
        liquidity_score=liquidity_score,
        correlation=correlation,
        btc_dominance=btc_dom,
        eth_dominance=eth_dom,
        funding_rate=funding,
        open_interest=oi,
        macro_context="neutral",
        regime=regime_str,
        regime_confidence=regime_confidence,
        adx=adx,
        rvol=rvol,
        rsi=rsi,
        atr_percent=atr_pct,
        confidence=confidence,
        health=1.0,
        skill_health=skill_health or {},
        active_skills=active_skills or [],
    )
