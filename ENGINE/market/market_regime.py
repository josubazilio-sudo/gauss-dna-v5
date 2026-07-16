import logging
from typing import Tuple

from .market_types import TrendDirection, MarketRegime
from .market_config import TREND_ADX_THRESHOLD

log = logging.getLogger(__name__)


def detect_regime(
    trend: TrendDirection,
    trend_strength: float,
    adx: float,
    atr_percent: float,
    rsi: float,
    bb_width: float,
    rvol: float,
    kalman_direction: str,
    kalman_tendency: float,
    ema50: float = 0.0,
    ema200: float = 0.0,
    current_price: float = 0.0,
    volume_crescente: bool = False,
) -> Tuple[MarketRegime, float]:
    is_high_adx = adx > TREND_ADX_THRESHOLD
    is_very_high_adx = adx > 35
    is_low_adx = adx < 20

    is_high_vol = atr_percent > 0.02 or bb_width > 0.08
    is_low_vol = atr_percent < 0.003 and bb_width < 0.03
    is_compression_vol = atr_percent < 0.005 and bb_width < 0.04

    is_rsi_extreme = rsi >= 72 or rsi <= 28
    is_rsi_oversold = rsi <= 30
    is_rsi_overbought = rsi >= 70

    kalman_up = kalman_direction.upper() == "UP"
    kalman_down = kalman_direction.upper() == "DOWN"
    kalman_side = kalman_direction.upper() in ("SIDE", "NEUTRAL", "")

    ema_bullish = (ema50 > ema200) if ema50 > 0 and ema200 > 0 else (trend == TrendDirection.BULLISH)
    ema_bearish = (ema50 < ema200) if ema50 > 0 and ema200 > 0 else (trend == TrendDirection.BEARISH)

    is_fluxo_comprador = rvol > 1.2 and kalman_up and trend == TrendDirection.BULLISH
    is_fluxo_vendedor = rvol > 1.2 and kalman_down and trend == TrendDirection.BEARISH

    is_divergence = (
        (is_rsi_overbought and kalman_down and trend == TrendDirection.BULLISH) or
        (is_rsi_oversold and kalman_up and trend == TrendDirection.BEARISH)
    )

    # 1. EXHAUSTION
    if is_rsi_extreme and (is_divergence or (not volume_crescente and is_high_adx)):
        confidence = min(abs(rsi - 50) / 50, 1.0)
        return MarketRegime.EXHAUSTION, round(confidence, 4)

    # 2. COMPRESSION
    if is_compression_vol and is_low_adx and rvol < 1.0:
        confidence = 0.5 + (1.0 - atr_percent / 0.005 if atr_percent < 0.005 else 0.0)
        return MarketRegime.COMPRESSION, round(min(confidence, 1.0), 4)

    # 3. STRONG TREND UP
    if is_high_adx and ema_bullish and kalman_up and is_fluxo_comprador:
        confidence = 0.5 + (adx / 100) * 0.3 + trend_strength * 0.2
        return MarketRegime.STRONG_TREND_UP, round(min(confidence, 1.0), 4)
    if is_high_adx and ema_bullish and kalman_up and trend == TrendDirection.BULLISH:
        confidence = 0.5 + trend_strength * 0.3
        return MarketRegime.STRONG_TREND_UP, round(min(confidence, 1.0), 4)
    if is_very_high_adx and trend == TrendDirection.BULLISH and rvol >= 1.0:
        confidence = 0.6 + trend_strength * 0.3
        return MarketRegime.STRONG_TREND_UP, round(min(confidence, 1.0), 4)

    # 4. STRONG TREND DOWN
    if is_high_adx and ema_bearish and kalman_down and is_fluxo_vendedor:
        confidence = 0.5 + (adx / 100) * 0.3 + trend_strength * 0.2
        return MarketRegime.STRONG_TREND_DOWN, round(min(confidence, 1.0), 4)
    if is_high_adx and ema_bearish and kalman_down and trend == TrendDirection.BEARISH:
        confidence = 0.5 + trend_strength * 0.3
        return MarketRegime.STRONG_TREND_DOWN, round(min(confidence, 1.0), 4)
    if is_very_high_adx and trend == TrendDirection.BEARISH and rvol >= 1.0:
        confidence = 0.6 + trend_strength * 0.3
        return MarketRegime.STRONG_TREND_DOWN, round(min(confidence, 1.0), 4)

    # 5. RANGING (lateral)
    if is_low_adx or (trend == TrendDirection.NEUTRAL and not is_high_vol):
        confidence = 0.5 if is_low_adx else 0.4
        return MarketRegime.RANGING, round(confidence, 4)

    # fallback: ranging com confiança baixa
    return MarketRegime.RANGING, 0.3


# Mantido para compatibilidade com código legado
def classify_regime(
    trend: TrendDirection,
    trend_strength: float,
    adx: float,
    atr_percent: float,
    rsi: float,
    bb_width: float,
    rvol: float,
) -> Tuple[MarketRegime, float]:
    return detect_regime(
        trend=trend,
        trend_strength=trend_strength,
        adx=adx,
        atr_percent=atr_percent,
        rsi=rsi,
        bb_width=bb_width,
        rvol=rvol,
        kalman_direction="UNKNOWN",
        kalman_tendency=0.0,
    )
