from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class SignalClassification(Enum):
    OURO_SUPREMO = "ouro_supremo"
    OURO = "ouro"
    PRATA = "prata"
    BRONZE = "bronze"
    REPROVADO = "reprovado"


class SignalDirection(Enum):
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"


class PatternType(Enum):
    ORDER_BLOCK = "order_block"
    FVG = "fvg"
    LIQUIDITY_SWEEP = "liquidity_sweep"
    BOS = "bos"
    CHOCH = "choch"
    MARKET_STRUCTURE_BREAK = "market_structure_break"


class StructureType(Enum):
    UPTREND = "uptrend"
    DOWNTREND = "downtrend"
    RANGING = "ranging"
    REVERSAL = "reversal"


@dataclass
class SwingPoint:
    price: float
    index: int
    high: bool


@dataclass
class Pattern:
    type: PatternType
    direction: SignalDirection
    timeframe: str
    price: float
    confidence: float
    strength: float
    description: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MarketStructure:
    structure_type: StructureType
    swing_highs: List[SwingPoint]
    swing_lows: List[SwingPoint]
    last_break: Optional[str] = None
    structure_strength: float = 0.0
    mm50: float = 0.0
    mm200: float = 0.0
    vwap: float = 0.0
    vwap_distance: float = 0.0
    mm50_distance: float = 0.0
    mm200_distance: float = 0.0
    mm50_trend: str = "neutral"
    mm200_trend: str = "neutral"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "structure_type": self.structure_type.value,
            "last_break": self.last_break,
            "structure_strength": self.structure_strength,
            "mm50": self.mm50,
            "mm200": self.mm200,
            "vwap": self.vwap,
            "vwap_distance": self.vwap_distance,
            "mm50_distance": self.mm50_distance,
            "mm200_distance": self.mm200_distance,
            "mm50_trend": self.mm50_trend,
            "mm200_trend": self.mm200_trend,
        }


@dataclass
class TimeframeAnalysis:
    timeframe: str
    patterns: List[Pattern]
    structure: MarketStructure
    score: float = 0.0


@dataclass
class ScannerScore:
    institutional_score: float = 0.0
    structural_score: float = 0.0
    market_score: float = 0.0
    momentum_score: float = 0.0
    liquidity_score: float = 0.0
    risk_score: float = 0.0
    confidence_score: float = 0.0
    quality_score: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "institutional_score": self.institutional_score,
            "structural_score": self.structural_score,
            "market_score": self.market_score,
            "momentum_score": self.momentum_score,
            "liquidity_score": self.liquidity_score,
            "risk_score": self.risk_score,
            "confidence_score": self.confidence_score,
            "quality_score": self.quality_score,
        }


@dataclass
class Signal:
    ticker: str
    timeframe: str
    direction: SignalDirection
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    risk_reward: float
    scores: ScannerScore
    classification: SignalClassification
    patterns: List[Pattern]
    structure: MarketStructure
    setup: str
    context: str
    approval_reasons: List[str]
    rejection_reasons: List[str]
    confidence: float
    quality: float
    timestamp: datetime = field(default_factory=lambda: datetime.now())
    market_context: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "timeframe": self.timeframe,
            "direction": self.direction.value,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit_1": self.take_profit_1,
            "take_profit_2": self.take_profit_2,
            "risk_reward": self.risk_reward,
            "scores": self.scores.to_dict(),
            "classification": self.classification.value,
            "patterns": [p.type.value for p in self.patterns],
            "structure": self.structure.to_dict(),
            "setup": self.setup,
            "context": self.context,
            "confidence": self.confidence,
            "quality": self.quality,
            "approval_reasons": self.approval_reasons,
            "rejection_reasons": self.rejection_reasons,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ScanReport:
    pair: str
    timestamp: datetime
    timeframes_analyzed: int
    total_patterns_found: int
    signals: List[Signal]
    errors: List[str] = field(default_factory=list)
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pair": self.pair,
            "timestamp": self.timestamp.isoformat(),
            "timeframes_analyzed": self.timeframes_analyzed,
            "total_patterns_found": self.total_patterns_found,
            "signals": [s.to_dict() for s in self.signals],
            "errors": self.errors,
            "duration_ms": self.duration_ms,
        }
