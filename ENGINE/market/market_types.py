from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class TrendDirection(Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class MarketRegime(Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"
    REVERSAL = "reversal"
    CALM = "calm"


class RsiZone(Enum):
    OVERBOUGHT = "overbought"
    OVERSOLD = "oversold"
    NORMAL = "normal"


class VolatilityZone(Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    EXTREME = "extreme"


class Timeframe(Enum):
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"


@dataclass
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class TechnicalIndicators:
    atr: float = 0.0
    atr_percent: float = 0.0
    adx: float = 0.0
    rsi: float = 50.0
    rvol: float = 1.0
    volume: float = 0.0
    avg_volume: float = 0.0
    bb_upper: float = 0.0
    bb_middle: float = 0.0
    bb_lower: float = 0.0
    bb_width: float = 0.0
    bb_position: float = 0.5
    ema_9: float = 0.0
    ema_21: float = 0.0
    ema_50: float = 0.0
    ema_200: float = 0.0
    ema_alignment: float = 0.0
    high_low_ratio: float = 0.0
    body_ratio: float = 0.0


@dataclass
class TimeframeContext:
    timeframe: str
    indicators: TechnicalIndicators
    trend: TrendDirection
    trend_strength: float
    regime: MarketRegime
    regime_confidence: float


@dataclass
class MarketContext:
    pair: str
    timestamp: datetime
    price: float
    indicators: TechnicalIndicators
    trend: TrendDirection
    trend_strength: float
    regime: MarketRegime
    regime_confidence: float
    funding_rate: float = 0.0
    spread: float = 0.0
    btc_correlation: float = 0.0
    eth_correlation: float = 0.0
    btc_dominance: float = 0.0
    open_interest: Optional[float] = None
    timeframes: Dict[str, TimeframeContext] = field(default_factory=dict)
    trend_score: float = 0.0
    momentum_score: float = 0.0
    volatility_score: float = 0.0
    liquidity_score: float = 0.0
    risk_score: float = 1.0
    confidence_score: float = 0.0
    institutional_score: float = 0.0
    market_score: float = 0.0
    rsi_zone: RsiZone = RsiZone.NORMAL
    volatility_zone: VolatilityZone = VolatilityZone.MODERATE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pair": self.pair,
            "timestamp": self.timestamp.isoformat(),
            "price": self.price,
            "trend": self.trend.value,
            "trend_strength": self.trend_strength,
            "regime": self.regime.value,
            "regime_confidence": self.regime_confidence,
            "atr_percent": self.indicators.atr_percent,
            "adx": self.indicators.adx,
            "rsi": self.indicators.rsi,
            "rvol": self.indicators.rvol,
            "bb_width": self.indicators.bb_width,
            "funding_rate": self.funding_rate,
            "spread": self.spread,
            "btc_correlation": self.btc_correlation,
            "btc_dominance": self.btc_dominance,
            "market_score": self.market_score,
            "trend_score": self.trend_score,
            "momentum_score": self.momentum_score,
            "volatility_score": self.volatility_score,
            "liquidity_score": self.liquidity_score,
            "risk_score": self.risk_score,
            "confidence_score": self.confidence_score,
            "institutional_score": self.institutional_score,
        }
