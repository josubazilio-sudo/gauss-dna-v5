import logging
from datetime import datetime
from typing import Dict, Any, Optional
from .scanner_types import SignalCandidate, SignalDecision, SignalDirection, PatternType
from .evidence_registry import EvidenceRegistry

log = logging.getLogger(__name__)

log.warning("V6 scanner/decision_engine.py importado — DEPRECATED. Usar ENGINE/decision/decision_engine.py (V7)")

class DecisionEngine:
    def __init__(self, version: str = "6.0"):
        self.version = version
        self.registry = EvidenceRegistry()

    def process(self, candidate: SignalCandidate) -> SignalDecision:
        # 1. Hard Filters (Eliminatory)
        reasons = []
        
        # Pattern checks
        patterns_ok = len(candidate.patterns) >= 1
        if not patterns_ok: reasons.append("patterns_ok_fail")

        # RVOL / Spread / ADX / ATR
        rvol_ok = candidate.rvol >= 0.5
        if not rvol_ok: reasons.append("rvol_fail")
        
        spread_ok = candidate.spread <= 0.01
        if not spread_ok: reasons.append("spread_fail")
        
        adx_ok = candidate.adx >= 15
        if not adx_ok: reasons.append("adx_fail")
        
        atr_ok = 0.0005 <= candidate.atr <= 0.08
        if not atr_ok: reasons.append("atr_fail")

        # SMC Checks
        bos = any(p.type == PatternType.BOS for p in candidate.patterns)
        choch = any(p.type == PatternType.CHOCH for p in candidate.patterns)
        fvg = any(p.type == PatternType.FVG for p in candidate.patterns)
        liquidity_sweep = any(p.type == PatternType.LIQUIDITY_SWEEP for p in candidate.patterns)

        # Lateral Market Logic
        score_penalty = 0.0
        lateral_approved = False
        
        if candidate.lateral_market_score > 0.8:
            reasons.append("Mercado_lateral_excessivo")
        elif candidate.lateral_market_score > 0.6:
            score_penalty = 0.3
        elif candidate.lateral_market_score > 0.3:
            score_penalty = 0.1
            
        has_smc_confirmation = any(p.type in [PatternType.BOS, PatternType.CHOCH] for p in candidate.patterns)
        if has_smc_confirmation and candidate.rvol >= 1.0:
            lateral_approved = True
            score_penalty = 0.0
            
        approved = len(reasons) == 0 and (not candidate.lateral_market_score > 0.8 or lateral_approved)
        reject_reason = ";".join(reasons) if not approved else None

        # Build Decision
        decision = SignalDecision(
            trace_id=candidate.trace_id,
            symbol=candidate.symbol,
            timeframe=candidate.timeframe,
            direction=candidate.direction.value,
            approved=approved,
            reject_reason=reject_reason,
            entry_price=candidate.current_price,
            stop_loss=0.0,
            tp1=0.0,
            tp2=0.0,
            entry_zone_valid=True,
            entry_score=candidate.scores.entry_score - score_penalty,
            quality=candidate.scores.quality_score - score_penalty,
            confidence=candidate.scores.confidence_score,
            risk=candidate.scores.risk_score,
            consensus=candidate.scores.consensus_score,
            conviction=candidate.scores.conviction_score,
            institutional_score=candidate.scores.institutional_score,
            structural_score=candidate.scores.structural_score,
            market_score=candidate.scores.market_score,
            liquidity_score=candidate.scores.liquidity_score,
            trend="neutral",
            trend_ok=True,
            structure_ok=True,
            market_ok=True,
            volume_ok=True,
            rvol_ok=rvol_ok,
            spread_ok=spread_ok,
            adx_ok=adx_ok,
            atr_ok=atr_ok,
            patterns_ok=patterns_ok,
            bos=bos,
            choch=choch,
            fvg=fvg,
            liquidity_sweep=liquidity_sweep,
            selected_order_block={},
            timestamp=datetime.utcnow(),
            engine_version=self.version
        )
        
        # Registrar evidência
        self.registry.register_decision(decision, candidate)
        
        return decision
