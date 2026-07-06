import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from .market_types import (
    Candle, MarketContext, TechnicalIndicators,
    TimeframeContext, TrendDirection,
)
from .market_trend import analyze_trend, compute_all_emas, compute_adx, compute_slope
from .market_momentum import analyze_momentum, classify_rsi
from .market_volatility import analyze_volatility, classify_volatility
from .market_liquidity import analyze_liquidity
from .market_regime import classify_regime
from .market_scoring import compute_all_scores

log = logging.getLogger(__name__)


class MarketEngine:
    def __init__(self):
        self._last_context: Optional[MarketContext] = None

    def analyze(
        self,
        pair: str,
        candles: List[Candle],
        funding_rate: float = 0.0,
        spread: float = 0.0,
        btc_correlation: float = 0.0,
        eth_correlation: float = 0.0,
        btc_dominance: float = 0.0,
        open_interest: Optional[float] = None,
        timeframe_candles: Optional[Dict[str, List[Candle]]] = None,
    ) -> MarketContext:
        if not candles:
            raise ValueError("At least one candle is required")

        price = candles[-1].close
        timestamp = datetime.now(timezone.utc)

        trend_dir, trend_strength = analyze_trend(candles)
        rsi, rvol, avg_volume, volume = analyze_momentum(candles)
        atr, atr_percent, bb_mid, bb_upper, bb_lower, bb_width, bb_pos = analyze_volatility(candles)
        ema_9, ema_21, ema_50, ema_200 = compute_all_emas(candles)
        adx = compute_adx(candles)
        slope = compute_slope(candles)
        regime, regime_conf = classify_regime(
            trend_dir, trend_strength, adx, atr_percent, rsi, bb_width, rvol,
        )
        rsi_zone = classify_rsi(rsi)
        vol_zone = classify_volatility(atr_percent)

        liquidity_s, spread_s, funding_s = analyze_liquidity(spread, funding_rate, rvol, avg_volume)

        high = max(c.close for c in candles[-20:]) if len(candles) >= 20 else max(c.close for c in candles)
        low = min(c.close for c in candles[-20:]) if len(candles) >= 20 else min(c.close for c in candles)
        body_ratio = abs(candles[-1].close - candles[-1].open) / (candles[-1].high - candles[-1].low) if (candles[-1].high - candles[-1].low) > 0 else 0.0

        indicators = TechnicalIndicators(
            atr=atr,
            atr_percent=atr_percent,
            adx=adx,
            rsi=rsi,
            rvol=rvol,
            volume=volume,
            avg_volume=avg_volume,
            bb_upper=bb_upper,
            bb_middle=bb_mid,
            bb_lower=bb_lower,
            bb_width=bb_width,
            bb_position=bb_pos,
            ema_9=ema_9,
            ema_21=ema_21,
            ema_50=ema_50,
            ema_200=ema_200,
            ema_alignment=slope,
            high_low_ratio=(high - low) / price if price > 0 else 0.0,
            body_ratio=body_ratio,
        )

        scores = compute_all_scores(
            trend_dir, trend_strength, adx, rsi, rvol,
            atr_percent, bb_width, spread, funding_rate,
            liquidity_s, regime, regime_conf, rsi_zone, vol_zone,
        )

        timeframes_ctx: Dict[str, TimeframeContext] = {}
        if timeframe_candles:
            for tf, tf_candles in timeframe_candles.items():
                if len(tf_candles) < 5:
                    continue
                tf_trend, tf_strength = analyze_trend(tf_candles)
                tf_rsi, _, _, _ = analyze_momentum(tf_candles)
                tf_adx = compute_adx(tf_candles)
                tf_atr, tf_atr_p, _, _, _, tf_bb_w, _ = analyze_volatility(tf_candles)
                tf_rvol = _get_rvol(tf_candles)
                tf_regime, tf_conf = classify_regime(
                    tf_trend, tf_strength, tf_adx, tf_atr_p, tf_rsi, tf_bb_w, tf_rvol,
                )
                tf_slope = compute_slope(tf_candles, 10)
                tf_ema9 = compute_ema(tf_candles, 9)
                tf_ema21 = compute_ema(tf_candles, 21)
                tf_ema50 = compute_ema(tf_candles, 50)

                timeframes_ctx[tf] = TimeframeContext(
                    timeframe=tf,
                    indicators=TechnicalIndicators(
                        atr=tf_atr,
                        atr_percent=tf_atr_p,
                        adx=tf_adx,
                        rsi=tf_rsi,
                        rvol=tf_rvol,
                        volume=tf_candles[-1].volume if tf_candles else 0.0,
                        avg_volume=_get_avg_vol(tf_candles),
                        bb_width=tf_bb_w,
                        ema_alignment=tf_slope,
                    ),
                    trend=tf_trend,
                    trend_strength=tf_strength,
                    regime=tf_regime,
                    regime_confidence=tf_conf,
                )

        ctx = MarketContext(
            pair=pair,
            timestamp=timestamp,
            price=price,
            indicators=indicators,
            trend=trend_dir,
            trend_strength=trend_strength,
            regime=regime,
            regime_confidence=regime_conf,
            funding_rate=funding_rate,
            spread=spread,
            btc_correlation=btc_correlation,
            eth_correlation=eth_correlation,
            btc_dominance=btc_dominance,
            open_interest=open_interest,
            timeframes=timeframes_ctx,
            trend_score=scores["trend_score"],
            momentum_score=scores["momentum_score"],
            volatility_score=scores["volatility_score"],
            liquidity_score=scores["liquidity_score"],
            risk_score=scores["risk_score"],
            confidence_score=scores["confidence_score"],
            institutional_score=scores["institutional_score"],
            market_score=scores["market_score"],
            rsi_zone=rsi_zone,
            volatility_zone=vol_zone,
        )
        self._last_context = ctx
        return ctx

    def last_context(self) -> Optional[MarketContext]:
        return self._last_context


def _get_rvol(candles: List[Candle]) -> float:
    if len(candles) < 21:
        return 1.0
    current = candles[-1].volume
    vols = [c.volume for c in candles[-21:-1]]
    avg = sum(vols) / len(vols) if vols else 1.0
    return current / avg if avg > 0 else 1.0


def _get_avg_vol(candles: List[Candle]) -> float:
    if len(candles) < 20:
        return sum(c.volume for c in candles) / len(candles) if candles else 0.0
    vols = [c.volume for c in candles[-20:]]
    return sum(vols) / 20.0


def compute_ema(candles: List[Candle], period: int) -> float:
    closes = [c.close for c in candles]
    if len(closes) < period:
        return closes[-1] if closes else 0.0
    multiplier = 2.0 / (period + 1)
    ema = sum(closes[:period]) / period
    for v in closes[period:]:
        ema = (v - ema) * multiplier + ema
    return ema
