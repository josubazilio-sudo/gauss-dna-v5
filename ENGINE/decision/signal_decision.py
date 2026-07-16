from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ENGINE.scanner.scanner_types import Signal, PatternType, SignalDirection


@dataclass
class SignalDecision:
    symbol: str = ""
    timeframe: str = ""
    trace_id: str = ""
    decision_id: str = ""

    approved: bool = False
    reject_reason: str = ""

    direction: str = ""
    trend: str = ""
    market_regime: str = ""

    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit_1: float = 0.0
    take_profit_2: float = 0.0
    risk_reward: float = 0.0

    entry_score: float = 0.0
    entry_zone_valid: bool = False
    entry_zone_status: str = ""

    # None = gate nunca avaliado (evaluate_signal() saiu num gate anterior,
    # ver ENGINE/decision/decision_engine.py). False = avaliado e reprovado.
    # True = avaliado e aprovado. Antes desses campos serem Optional, todos
    # tinham default bool=False — o log TRACE[...] GateResults (via
    # _log_result) exibia "trend=False struct=False ... rr=False" para
    # QUALQUER rejeicao no primeiro gate (ex.: RVOL), dando a falsa
    # impressao de que 12+ sistemas distintos reprovaram o sinal quando na
    # verdade apenas 1 gate rodou. all()/truthiness em todo o codebase
    # (main.py._decision_has_required_flags, etc.) tratam None como falsy,
    # identico a False, entao o resultado de aprovacao/rejeicao E IDENTICO
    # — so a fidelidade do diagnostico muda.
    quality_ok: Optional[bool] = None
    confidence_ok: Optional[bool] = None
    risk_ok: Optional[bool] = None
    entry_zone_ok: Optional[bool] = None
    entry_score_ok: Optional[bool] = None
    consensus_ok: Optional[bool] = None
    institutional_ok: Optional[bool] = None
    trend_ok: Optional[bool] = None
    structure_ok: Optional[bool] = None
    market_ok: Optional[bool] = None
    rvol_ok: Optional[bool] = None
    adx_ok: Optional[bool] = None
    spread_ok: Optional[bool] = None
    flow_ok: Optional[bool] = None
    timing_ok: Optional[bool] = None
    liquidity_ok: Optional[bool] = None
    structural_ok: Optional[bool] = None
    conviction_ok: Optional[bool] = None
    rr_ok: Optional[bool] = None

    quality: float = 0.0
    quality_score: float = 0.0
    confidence: float = 0.0
    risk: float = 0.0
    risk_score: float = 0.0
    institutional_score: float = 0.0
    structural_score: float = 0.0
    market_score: float = 0.0
    liquidity_score: float = 0.0
    flow_score: float = 0.0
    momentum_score: float = 0.0
    consensus: float = 0.0

    selected_order_block: str = ""
    signal_id: str = ""

    bos: int = 0
    choch: int = 0
    fvg: int = 0
    liquidity_sweep: int = 0

    timestamp: str = ""
    pipeline_hash: str = ""

    kalman_direction: str = "UNKNOWN"
    kalman_confidence: float = 0.0
    kalman_trend_state: str = "ranging"
    kalman_tendency: float = 0.0
    classification_label: str = "reprovado"
    penalty_reasons: list = field(default_factory=list)
    kalman_ok: Optional[bool] = None
    trend_gate_ok: Optional[bool] = None
    coherence: dict = field(default_factory=lambda: {})

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "pair": self.symbol,
            "timeframe": self.timeframe,
            "trace_id": self.trace_id,
            "decision_id": self.decision_id,
            "approved": self.approved,
            "reject_reason": self.reject_reason,
            "direction": self.direction,
            "trend": self.trend,
            "market_regime": self.market_regime,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit_1": self.take_profit_1,
            "take_profit_2": self.take_profit_2,
            "risk_reward": self.risk_reward,
            "entry_score": self.entry_score,
            "entry_zone_valid": self.entry_zone_valid,
            "entry_zone_status": self.entry_zone_status,
            "quality_ok": self.quality_ok,
            "confidence_ok": self.confidence_ok,
            "risk_ok": self.risk_ok,
            "entry_zone_ok": self.entry_zone_ok,
            "entry_score_ok": self.entry_score_ok,
            "consensus_ok": self.consensus_ok,
            "institutional_ok": self.institutional_ok,
            "trend_ok": self.trend_ok,
            "structure_ok": self.structure_ok,
            "market_ok": self.market_ok,
            "rvol_ok": self.rvol_ok,
            "adx_ok": self.adx_ok,
            "spread_ok": self.spread_ok,
            "flow_ok": self.flow_ok,
            "timing_ok": self.timing_ok,
            "liquidity_ok": self.liquidity_ok,
            "structural_ok": self.structural_ok,
            "conviction_ok": self.conviction_ok,
            "rr_ok": self.rr_ok,
            "quality": self.quality,
            "quality_score": self.quality_score,
            "confidence": self.confidence,
            "risk": self.risk,
            "risk_score": self.risk_score,
            "institutional_score": self.institutional_score,
            "structural_score": self.structural_score,
            "market_score": self.market_score,
            "liquidity_score": self.liquidity_score,
            "flow_score": self.flow_score,
            "momentum_score": self.momentum_score,
            "consensus": self.consensus,
            "selected_order_block": self.selected_order_block,
            "signal_id": self.signal_id,
            "bos": self.bos,
            "choch": self.choch,
            "fvg": self.fvg,
            "liquidity_sweep": self.liquidity_sweep,
            "pipeline_hash": self.pipeline_hash,
            "timestamp": self.timestamp,
            "kalman_direction": self.kalman_direction,
            "kalman_confidence": self.kalman_confidence,
            "kalman_trend_state": self.kalman_trend_state,
            "kalman_tendency": self.kalman_tendency,
            "classification_label": self.classification_label,
            "penalty_reasons": self.penalty_reasons,
        }

    @staticmethod
    def from_signal(signal: Signal) -> "SignalDecision":
        import uuid
        scores = signal.scores
        direction = str(signal.direction.value) if hasattr(signal.direction, "value") else str(signal.direction)

        patterns = signal.patterns or []
        bos_count = sum(1 for p in patterns if p.type == PatternType.BOS)
        choch_count = sum(1 for p in patterns if p.type == PatternType.CHOCH)
        ob_count = sum(1 for p in patterns if p.type == PatternType.ORDER_BLOCK)
        fvg_count = sum(1 for p in patterns if p.type == PatternType.FVG)
        sweep_count = sum(1 for p in patterns if p.type == PatternType.LIQUIDITY_SWEEP)

        all_zones = [p for p in patterns if p.type in (PatternType.ORDER_BLOCK, PatternType.FVG)]
        ob_ids = [f"{p.type.value}@{p.price:.2f}" for p in all_zones[:3]]
        selected_ob = ", ".join(ob_ids) if ob_ids else "none"

        trace_id = signal.signal_id or str(uuid.uuid4())[:8]

        return SignalDecision(
            symbol=signal.ticker,
            timeframe=signal.timeframe,
            trace_id=trace_id,
            signal_id=signal.signal_id,
            decision_id=str(uuid.uuid4())[:8],
            direction=direction,
            market_regime=str(signal.regime),
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            take_profit_1=signal.take_profit_1,
            take_profit_2=signal.take_profit_2,
            risk_reward=signal.risk_reward,
            entry_score=scores.entry_score if scores else 0.0,
            entry_zone_status=signal.entry_zone,
            quality=scores.quality_score if scores else 0.0,
            quality_score=scores.quality_score if scores else 0.0,
            confidence=signal.confidence,
            risk=scores.risk_score if scores else 0.0,
            risk_score=scores.risk_score if scores else 0.0,
            institutional_score=scores.institutional_score if scores else 0.0,
            structural_score=scores.structural_score if scores else 0.0,
            market_score=scores.market_score if scores else 0.0,
            liquidity_score=scores.liquidity_score if scores else 0.0,
            flow_score=scores.flow_score if scores else 0.0,
            momentum_score=scores.momentum_score if scores else 0.0,
            consensus=scores.consensus_score if scores else 0.0,
            selected_order_block=selected_ob,
            bos=bos_count,
            choch=choch_count,
            fvg=fvg_count,
            liquidity_sweep=sweep_count,
            timestamp=datetime.now(timezone.utc).isoformat(),
            trend=str(signal.regime).title() if signal.regime and signal.regime != "unknown" else "",
            kalman_direction=getattr(signal, 'kalman_direction', 'UNKNOWN'),
            kalman_confidence=getattr(signal, 'kalman_confidence', 0.0),
            kalman_trend_state=getattr(signal, 'kalman_trend_state', 'ranging'),
            kalman_tendency=getattr(signal, 'kalman_tendency', 0.0),
            classification_label=getattr(signal, 'classification_label', 'reprovado'),
            penalty_reasons=getattr(signal, 'penalty_reasons', []),
        )

    @staticmethod
    def _to_direction(dir_str: str) -> SignalDirection:
        if dir_str.lower() in ("long", "buy"):
            return SignalDirection.LONG
        if dir_str.lower() in ("short", "sell"):
            return SignalDirection.SHORT
        return SignalDirection.NEUTRAL
