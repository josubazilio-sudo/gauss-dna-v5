import unittest
import os
import shutil
from datetime import datetime
from typing import Any, Dict, List, Optional

from ENGINE.scanner.scanner_types import (
    Signal, ScannerScore, SignalDirection, SignalClassification,
    Pattern, PatternType, MarketStructure, StructureType,
    SwingPoint, EntryZone, EntryDetails,
)
from ENGINE.decision.decision_engine import DecisionEngine, SignalDecision
from ENGINE.decision.self_audit import SelfAuditEngine, SelfAuditResult, AuditEntry, FAIL_SAFE_DIR


def _make_signal(
    ticker: str = "BTCUSDT",
    timeframe: str = "1h",
    direction: SignalDirection = SignalDirection.LONG,
    entry_price: float = 50000.0,
    stop_loss: float = 49000.0,
    take_profit_1: float = 52000.0,
    take_profit_2: float = 54000.0,
    quality_score: float = 0.80,
    confidence_score: float = 0.80,
    entry_score: float = 0.6,
    consensus_score: float = 0.7,
    risk_score: float = 0.30,
    institutional_score: float = 0.85,
    structural_score: float = 0.70,
    market_score: float = 0.5,
    momentum_score: float = 0.5,
    liquidity_score: float = 0.70,
    conviction_score: float = 0.60,
    flow_score: float = 0.5,
    follow_through: float = 0.5,
    timing_index: float = 0.60,
    structure_strength: float = 0.5,
    adx: float = 25.0,
    rvol: float = 1.5,
    atr: float = 500.0,
    regime: str = "uptrend",
    patterns: Optional[List[Pattern]] = None,
    rejection_reasons: Optional[List[str]] = None,
    entry_details: Optional[EntryDetails] = None,
) -> Signal:
    scores = ScannerScore(
        institutional_score=institutional_score,
        structural_score=structural_score,
        market_score=market_score,
        momentum_score=momentum_score,
        liquidity_score=liquidity_score,
        risk_score=risk_score,
        confidence_score=confidence_score,
        quality_score=quality_score,
        entry_score=entry_score,
        consensus_score=consensus_score,
        conviction_score=conviction_score,
        flow_score=flow_score,
        follow_through=follow_through,
        timing_index=timing_index,
    )

    if patterns is None:
        patterns = [
            Pattern(
                type=PatternType.ORDER_BLOCK,
                direction=direction,
                timeframe=timeframe,
                price=entry_price,
                confidence=0.8,
                strength=0.7,
                description="OB teste",
                metadata={"upper": entry_price + 100, "lower": entry_price - 100, "index": 10},
            ),
            Pattern(
                type=PatternType.BOS,
                direction=direction,
                timeframe=timeframe,
                price=entry_price,
                confidence=0.7,
                strength=0.6,
                description="BOS teste",
                metadata={"index": 12},
            ),
        ]

    structure = MarketStructure(
        structure_type=StructureType.UPTREND if direction == SignalDirection.LONG else StructureType.DOWNTREND,
        swing_highs=[],
        swing_lows=[],
        structure_strength=structure_strength,
    )

    return Signal(
        ticker=ticker,
        timeframe=timeframe,
        direction=direction,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit_1=take_profit_1,
        take_profit_2=take_profit_2,
        risk_reward=2.0,
        scores=scores,
        classification=SignalClassification.OURO,
        patterns=patterns,
        structure=structure,
        setup="test",
        context="test",
        approval_reasons=[],
        rejection_reasons=rejection_reasons or [],
        confidence=scores.confidence_score,
        quality=scores.quality_score,
        rvol=rvol,
        adx=adx,
        atr_value=atr,
        regime=regime,
        structure_strength=structure_strength,
        entry_details=entry_details,
    )


class TestSelfAudit(unittest.TestCase):

    def setUp(self):
        self._clean_failsafe()
        os.makedirs(FAIL_SAFE_DIR, exist_ok=True)

    def tearDown(self):
        self._clean_failsafe()

    def _clean_failsafe(self):
        if os.path.exists(FAIL_SAFE_DIR):
            shutil.rmtree(FAIL_SAFE_DIR)

    # --- approved=True com todos os filtros OK → PASS ---

    def test_approved_all_ok_passes(self):
        sig = _make_signal()
        dr = DecisionEngine.evaluate_signal(sig, entry_details=sig.entry_details)
        audit = SelfAuditEngine.audit(dr, sig)
        self.assertTrue(audit.passed, "Sinal aprovado com todos filtros OK deve passar na auditoria")
        self.assertGreaterEqual(len(audit.entries), 12, "approved=True deve ter pelo menos 12 checks")

    # --- approved=True mas entry_zone_ok=False → BLOCKED ---

    def test_approved_entry_zone_false_blocked(self):
        dr = SignalDecision(
            approved=True,
            reject_reason="APROVADO",
            market_ok=True, trend_ok=True, structure_ok=True,
            entry_zone_ok=False, entry_score_ok=True,
            consensus_ok=True, quality_ok=True, confidence_ok=True,
            risk_ok=True, institutional_ok=True,
            selected_order_block="OB@50000",
            symbol="BTCUSDT", direction="long",
            trace_id="test-001",
        )
        audit = SelfAuditEngine.audit(dr)
        self.assertFalse(audit.passed)
        self.assertIn("entry_zone_ok", audit.block_reason)

    # --- approved=True mas consensus_ok=False → BLOCKED ---

    def test_approved_consensus_false_blocked(self):
        dr = SignalDecision(
            approved=True,
            reject_reason="APROVADO",
            market_ok=True, trend_ok=True, structure_ok=True,
            entry_zone_ok=True, entry_score_ok=True,
            consensus_ok=False, quality_ok=True, confidence_ok=True,
            risk_ok=True, institutional_ok=True,
            selected_order_block="OB@50000",
            symbol="BTCUSDT", direction="long",
            trace_id="test-002",
        )
        audit = SelfAuditEngine.audit(dr)
        self.assertFalse(audit.passed)
        self.assertIn("consensus_ok", audit.block_reason)

    # --- approved=True mas quality_ok=False → BLOCKED ---

    def test_approved_quality_false_blocked(self):
        dr = SignalDecision(
            approved=True,
            reject_reason="APROVADO",
            market_ok=True, trend_ok=True, structure_ok=True,
            entry_zone_ok=True, entry_score_ok=True,
            consensus_ok=True, quality_ok=False, confidence_ok=True,
            risk_ok=True, institutional_ok=True,
            selected_order_block="OB@50000",
            symbol="BTCUSDT", direction="long",
            trace_id="test-003",
        )
        audit = SelfAuditEngine.audit(dr)
        self.assertFalse(audit.passed)

    # --- approved=True mas direction diverge do signal → BLOCKED ---

    def test_approved_direction_divergente_blocked(self):
        sig = _make_signal(direction=SignalDirection.LONG)
        dr = DecisionEngine.evaluate_signal(sig, entry_details=sig.entry_details)
        dr.direction = "short"
        audit = SelfAuditEngine.audit(dr, sig)
        self.assertFalse(audit.passed)
        self.assertIn("direction_consistent", audit.block_reason)

    # --- approved=True mas selected_order_block vazio → BLOCKED ---

    def test_approved_no_ob_selected_blocked(self):
        sig = _make_signal(entry_price=50000)
        dr = DecisionEngine.evaluate_signal(sig, entry_details=sig.entry_details)
        dr.selected_order_block = ""
        audit = SelfAuditEngine.audit(dr, sig)
        self.assertFalse(audit.passed)
        self.assertIn("selected_order_block", audit.block_reason)

    # --- approved=False com filtro False → PASS ---

    def test_rejected_with_false_filter_passes(self):
        sig = _make_signal(entry_score=0.1)
        entry_details = EntryDetails(entry_zone=EntryZone(50100, 49900, 50000, 0.1, "outside"),
            score=0.1, approved=False,
        )
        dr = DecisionEngine.evaluate_signal(sig, entry_details=entry_details)
        self.assertFalse(dr.approved)
        audit = SelfAuditEngine.audit(dr, sig)
        self.assertTrue(audit.passed,
                        "Sinal reprovado com filtro False deve passar na auditoria")

    # --- approved=False com todos filtros True → BUG detectado ---

    def test_rejected_all_filters_true_bug_detected(self):
        dr = SignalDecision(
            approved=False,
            reject_reason="Rejeitado manualmente",
            market_ok=True, trend_ok=True, structure_ok=True,
            entry_zone_ok=True, entry_score_ok=True,
            consensus_ok=True, quality_ok=True, confidence_ok=True,
            risk_ok=True, institutional_ok=True,
            selected_order_block="OB@50000",
            symbol="BTCUSDT", direction="long",
            trace_id="test-004",
        )
        audit = SelfAuditEngine.audit(dr)
        self.assertFalse(audit.passed,
                         "approved=False com todos filtros True deve ser detectado como BUG")
        self.assertIn("rejected_has_at_least_one_false_filter", audit.block_reason)

    # --- approved=True mas risk_ok=False → BLOCKED ---

    def test_approved_risk_false_blocked(self):
        dr = SignalDecision(
            approved=True,
            reject_reason="APROVADO",
            market_ok=True, trend_ok=True, structure_ok=True,
            entry_zone_ok=True, entry_score_ok=True,
            consensus_ok=True, quality_ok=True, confidence_ok=True,
            risk_ok=False, institutional_ok=True,
            selected_order_block="OB@50000",
            symbol="BTCUSDT", direction="long",
            trace_id="test-005",
        )
        audit = SelfAuditEngine.audit(dr)
        self.assertFalse(audit.passed)

    # --- Snapshot salvo em caso de bloqueio ---

    def test_snapshot_saved_on_block(self):
        dr = SignalDecision(
            approved=True,
            reject_reason="APROVADO",
            market_ok=True, trend_ok=True, structure_ok=True,
            entry_zone_ok=False, entry_score_ok=True,
            consensus_ok=True, quality_ok=True, confidence_ok=True,
            risk_ok=True, institutional_ok=True,
            selected_order_block="OB@50000",
            symbol="BTCUSDT", direction="long",
            trace_id="test-snap",
        )
        audit = SelfAuditEngine.audit(dr)
        self.assertFalse(audit.passed)
        self.assertTrue(os.path.exists(audit.snapshot_path),
                        "Snapshot deve ser salvo quando auditoria bloqueia")

    # --- SelfAuditResult.to_report() gera relatorio ---

    def test_report_generated(self):
        dr = SignalDecision(
            approved=True,
            reject_reason="APROVADO",
            market_ok=True, trend_ok=True, structure_ok=True,
            entry_zone_ok=False, entry_score_ok=True,
            consensus_ok=True, quality_ok=True, confidence_ok=True,
            risk_ok=True, institutional_ok=True,
            selected_order_block="OB@50000",
            symbol="BTCUSDT", direction="long",
            trace_id="test-rpt",
        )
        audit = SelfAuditEngine.audit(dr)
        report = audit.to_report()
        self.assertIn("SELF AUDIT REPORT", report)
        self.assertIn("entry_zone_ok", report)
        self.assertIn("BLOCKED", report)


if __name__ == "__main__":
    unittest.main()
