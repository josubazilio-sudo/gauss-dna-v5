import logging
from typing import Dict

from .market_types import TrendDirection, MarketRegime, RsiZone, VolatilityZone
from .market_config import SCORE_WEIGHTS, RSI_OVERBOUGHT, RSI_OVERSOLD

log = logging.getLogger(__name__)


def score_trend(trend: TrendDirection, strength: float, adx: float) -> float:
    if trend == TrendDirection.NEUTRAL:
        return round(strength * 0.3, 4)
    if trend == TrendDirection.BULLISH:
        s = 0.5 + strength * 0.4 + min(adx / 50.0, 0.3)
        return round(min(s, 1.0), 4)
    s = 0.5 + strength * 0.4 + min(adx / 50.0, 0.3)
    return round(min(s, 1.0), 4)


def score_momentum(rsi: float, rvol: float) -> float:
    rvol_score = min(rvol / 2.0, 1.0) * 0.4
    if rsi <= RSI_OVERSOLD:
        rsi_score = 0.7 + (RSI_OVERSOLD - rsi) / 100.0
    elif rsi >= RSI_OVERBOUGHT:
        rsi_score = 0.7 + (rsi - RSI_OVERBOUGHT) / 100.0
    else:
        rsi_score = 0.3 + (rsi - RSI_OVERSOLD) / (RSI_OVERBOUGHT - RSI_OVERSOLD) * 0.4
    return round(min(rsi_score * 0.6 + rvol_score, 1.0), 4)


def score_volatility(atr_percent: float, bb_width: float) -> float:
    if atr_percent < 0.003:
        return round(max(0.3, atr_percent / 0.003 * 0.5), 4)
    if atr_percent < 0.008:
        return round(0.5 + (atr_percent - 0.003) / 0.005 * 0.4, 4)
    if atr_percent < 0.02:
        return round(0.9 - (atr_percent - 0.008) / 0.012 * 0.4, 4)
    return round(max(0.2, 0.5 - (atr_percent - 0.02) / 0.02 * 0.3), 4)


def score_risk(
    atr_percent: float, spread: float, funding: float,
    volatility_score: float, liquidity_score: float,
) -> float:
    vol_risk = 1.0 - volatility_score
    spread_risk = 1.0 - min(spread / 0.005, 1.0)
    funding_risk = 1.0 - min(abs(funding) / 0.02, 1.0)
    composite = vol_risk * 0.3 + spread_risk * 0.25 + funding_risk * 0.25 + liquidity_score * 0.2
    return round(min(composite, 1.0), 4)


def score_confidence(
    trend: TrendDirection, regime: MarketRegime,
    regime_confidence: float, rsi_zone: RsiZone,
    volatility_zone: VolatilityZone,
) -> float:
    base = regime_confidence
    if regime in (
        MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN,
        MarketRegime.STRONG_TREND_UP, MarketRegime.STRONG_TREND_DOWN,
    ) and trend != TrendDirection.NEUTRAL:
        base += 0.2
    if rsi_zone == RsiZone.NORMAL:
        base += 0.1
    elif rsi_zone in (RsiZone.OVERBOUGHT, RsiZone.OVERSOLD):
        base += 0.05
    if volatility_zone == VolatilityZone.EXTREME:
        base -= 0.2
    elif volatility_zone == VolatilityZone.LOW:
        base -= 0.1
    return round(max(0.0, min(base, 1.0)), 4)


def score_institutional(
    trend_score: float, momentum_score: float,
    volatility_score: float, liquidity_score: float,
    risk_score: float, confidence_score: float,
) -> float:
    weights = SCORE_WEIGHTS["institutional_score"]
    composite = (
        trend_score * weights["trend"] +
        momentum_score * weights["momentum"] +
        volatility_score * weights["volatility"] +
        liquidity_score * weights["liquidity"] +
        risk_score * weights["risk"] +
        confidence_score * weights["confidence"]
    )
    return round(composite, 4)


def score_market(
    trend_score: float, momentum_score: float,
    volatility_score: float, liquidity_score: float,
    risk_score: float, confidence_score: float,
) -> float:
    weights = SCORE_WEIGHTS["market_score"]
    composite = (
        trend_score * weights["trend"] +
        momentum_score * weights["momentum"] +
        volatility_score * weights["volatility"] +
        liquidity_score * weights["liquidity"] +
        risk_score * weights["risk"] +
        confidence_score * weights["confidence"]
    )
    return round(composite, 4)


def compute_all_scores(
    trend: TrendDirection,
    trend_strength: float,
    adx: float,
    rsi: float,
    rvol: float,
    atr_percent: float,
    bb_width: float,
    spread: float,
    funding: float,
    liquidity_score: float,
    regime: MarketRegime,
    regime_confidence: float,
    rsi_zone: RsiZone,
    volatility_zone: VolatilityZone,
) -> Dict[str, float]:
    ts = score_trend(trend, trend_strength, adx)
    ms = score_momentum(rsi, rvol)
    vs = score_volatility(atr_percent, bb_width)
    rs = score_risk(atr_percent, spread, funding, vs, liquidity_score)
    cs = score_confidence(trend, regime, regime_confidence, rsi_zone, volatility_zone)
    inst = score_institutional(ts, ms, vs, liquidity_score, rs, cs)
    mk = score_market(ts, ms, vs, liquidity_score, rs, cs)
    return {
        "trend_score": ts,
        "momentum_score": ms,
        "volatility_score": vs,
        "liquidity_score": liquidity_score,
        "risk_score": rs,
        "confidence_score": cs,
        "institutional_score": inst,
        "market_score": mk,
    }
