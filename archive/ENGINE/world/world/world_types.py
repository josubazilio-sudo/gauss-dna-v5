import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


class MarketState(Enum):
    BULL = "bull"
    BEAR = "bear"
    STRONG_TREND_UP = "strong_trend_up"
    STRONG_TREND_DOWN = "strong_trend_down"
    WEAK_TREND_UP = "weak_trend_up"
    WEAK_TREND_DOWN = "weak_trend_down"
    RANGING = "ranging"
    ACCUMULATION = "accumulation"
    DISTRIBUTION = "distribution"
    EXPANSION = "expansion"
    COMPRESSION = "compression"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    UNCERTAIN = "uncertain"


class MarketQuality(Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    HOSTILE = "hostile"


@dataclass(frozen=True)
class WorldModel:
    version: str = "10.0.0"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    state: MarketState = MarketState.UNCERTAIN
    quality: MarketQuality = MarketQuality.FAIR
    global_trend: str = "neutral"
    local_trend: str = "neutral"
    trend_strength: float = 0.0
    volatility: str = "moderate"
    volatility_score: float = 0.0
    liquidity: str = "normal"
    liquidity_score: float = 0.0
    correlation: float = 0.0
    btc_dominance: float = 0.0
    eth_dominance: float = 0.0
    funding_rate: float = 0.0
    open_interest: Optional[float] = None
    macro_context: str = "neutral"

    regime: str = "unknown"
    regime_confidence: float = 0.0
    adx: float = 0.0
    rvol: float = 0.0
    rsi: float = 50.0
    atr_percent: float = 0.0

    confidence: float = 0.0
    health: float = 1.0
    skill_health: Dict[str, float] = field(default_factory=dict)
    active_skills: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "timestamp": self.timestamp.isoformat(),
            "state": self.state.value,
            "quality": self.quality.value,
            "global_trend": self.global_trend,
            "local_trend": self.local_trend,
            "trend_strength": self.trend_strength,
            "volatility": self.volatility,
            "volatility_score": self.volatility_score,
            "liquidity": self.liquidity,
            "liquidity_score": self.liquidity_score,
            "correlation": self.correlation,
            "btc_dominance": self.btc_dominance,
            "eth_dominance": self.eth_dominance,
            "funding_rate": self.funding_rate,
            "open_interest": self.open_interest,
            "macro_context": self.macro_context,
            "regime": self.regime,
            "regime_confidence": self.regime_confidence,
            "adx": self.adx,
            "rvol": self.rvol,
            "rsi": self.rsi,
            "atr_percent": self.atr_percent,
            "confidence": self.confidence,
            "health": self.health,
            "active_skills": self.active_skills,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def compute_hash(self) -> str:
        raw = json.dumps(self.to_dict(), sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def is_tradeable(self) -> bool:
        return (
            self.state != MarketState.UNCERTAIN
            and self.quality not in (MarketQuality.POOR, MarketQuality.HOSTILE)
            and self.confidence >= 0.30
            and self.health >= 0.50
        )
