from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class SignalClassification(Enum):
    DIAMANTE = "diamante"
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
    entry_score: float = 0.0
    consensus_score: float = 0.0
    conviction_score: float = 0.0
    flow_score: float = 0.0
    follow_through: float = 0.0
    timing_index: float = 0.0

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
            "entry_score": self.entry_score,
            "consensus_score": self.consensus_score,
            "conviction_score": self.conviction_score,
            "flow_score": self.flow_score,
            "follow_through": self.follow_through,
            "timing_index": self.timing_index,
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
    penalty_reasons: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now())
    market_context: Optional[Dict[str, Any]] = None
    rvol: float = 0.0
    adx: float = 0.0
    regime: str = "unknown"
    entry_type: str = "a_mercado"
    atr_value: float = 0.0
    volume: float = 0.0
    ema50: float = 0.0
    ema200: float = 0.0
    vwap: float = 0.0
    structure_strength: float = 0.0
    false_breakout_clear: bool = False
    traps_clear: bool = False
    volume_above_avg: bool = False
    rvol_confirmed: bool = False
    no_absorption: bool = True
    no_rejection: bool = True
    structure_valid: bool = False
    signal_id: str = ""
    explanation: str = ""
    entry_zone: str = ""
    order_block_distance: float = 0.0
    fvg_distance: float = 0.0
    validity: str = ""
    entry_details: Optional["EntryDetails"] = None
    kalman_direction: str = "UNKNOWN"
    kalman_confidence: float = 0.0
    kalman_trend_state: str = "ranging"
    kalman_tendency: float = 0.0
    classification_label: str = "reprovado"

    @property
    def approved(self) -> bool:
        return len(self.rejection_reasons) == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "timestamp": self.timestamp.isoformat(),
            "ticker": self.ticker,
            "pair": self.ticker,
            "timeframe": self.timeframe,
            "direction": self.direction.value,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit_1": self.take_profit_1,
            "take_profit_2": self.take_profit_2,
            "risk_reward": self.risk_reward,
            "scores": self.scores.to_dict(),
            "classification": self.classification.value if self.classification else None,
            "patterns": [p.type.value for p in self.patterns],
            "structure": self.structure.to_dict() if self.structure else None,
            "setup": self.setup,
            "context": self.context,
            "confidence": self.confidence,
            "quality": self.quality,
            "approval_reasons": self.approval_reasons,
            "rejection_reasons": self.rejection_reasons,
            "penalty_reasons": self.penalty_reasons,
            "regime": self.regime,
            "entry_type": self.entry_type,
            "entry_zone": self.entry_zone,
            "order_block_distance": self.order_block_distance,
            "fvg_distance": self.fvg_distance,
            "validity": self.validity,
            "approved": self.approved,
            "rvol": self.rvol,
            "adx": self.adx,
            "atr": self.atr_value,
            "volume": self.volume,
            "ema50": self.ema50,
            "ema200": self.ema200,
            "vwap": self.vwap,
            "structure_strength": self.structure_strength,
            "market_context": self.market_context,
            "explanation": self.explanation,
            "kalman_direction": self.kalman_direction,
            "kalman_confidence": self.kalman_confidence,
            "kalman_trend_state": self.kalman_trend_state,
            "kalman_tendency": self.kalman_tendency,
            "classification_label": self.classification_label,
            "false_breakout_clear": self.false_breakout_clear,
            "traps_clear": self.traps_clear,
            "volume_above_avg": self.volume_above_avg,
            "rvol_confirmed": self.rvol_confirmed,
            "no_absorption": self.no_absorption,
            "no_rejection": self.no_rejection,
            "structure_valid": self.structure_valid,
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

@dataclass
class EntryDetails:
    entry_zone: "EntryZone"
    score: float
    is_valid: bool = True
    approved: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_zone": asdict(self.entry_zone),
            "score": self.score,
            "is_valid": self.is_valid,
            "approved": self.approved
        }

@dataclass
class EntryZone:
    upper_limit: float
    lower_limit: float
    ideal_price: float
    score: float
    status: str


@dataclass(frozen=True)
class SignalCandidate:
    trace_id: str
    symbol: str
    timeframe: str
    patterns: List[Pattern]
    structure: MarketStructure
    scores: ScannerScore
    rvol: float
    adx: float
    atr: float
    spread: float
    volume: float
    current_price: float
    direction: SignalDirection
    lateral_market_score: float
    entry_details: Optional[EntryDetails] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

@dataclass
class Penalty:
    reason: str
    weight: float
    source: str

@dataclass(frozen=True)
class SignalDecision:
    trace_id: str
    symbol: str
    timeframe: str
    direction: str
    approved: bool
    reject_reason: Optional[str]
    entry_price: float
    stop_loss: float
    tp1: float
    tp2: float
    entry_zone_valid: bool
    entry_score: float
    quality: float
    confidence: float
    risk: float
    consensus: float
    conviction: float
    institutional_score: float
    structural_score: float
    market_score: float
    liquidity_score: float
    trend: str
    trend_ok: bool
    structure_ok: bool
    market_ok: bool
    volume_ok: bool
    rvol_ok: bool
    spread_ok: bool
    adx_ok: bool
    atr_ok: bool
    patterns_ok: bool
    bos: bool
    choch: bool
    fvg: bool
    liquidity_sweep: bool
    selected_order_block: Dict[str, Any]
    timestamp: datetime
    engine_version: str



