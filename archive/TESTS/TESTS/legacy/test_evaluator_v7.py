"""
====================================================

LEGACY V7

Arquitetura:
Decision Engine V7

Status:
LEGADO

Producao:
NAO

Kernel V10:
NAO UTILIZA

Arquivo preservado apenas para documentacao historica.

====================================================
"""

import unittest
from datetime import datetime
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ENGINE.scanner.scanner_types import (
    Signal, ScannerScore, SignalDirection, SignalClassification,
    Pattern, PatternType, MarketStructure, StructureType,
    SwingPoint, EntryZone, EntryDetails,
)
from ENGINE.decision.decision_engine import DecisionEngine, SignalDecision
from ENGINE.scanner.scanner_config import (
    ENTRY_ZONE_SCORE_MIN,
    CONSENSUS_MINIMUM_SCORE,
    QUALITY_GATE_MIN_SCORE,
    QUALITY_GATE_CONFIDENCE_MIN,
    QUALITY_GATE_RISK_MAX,
)


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
        approval_reasons=["OK"],
        rejection_reasons=rejection_reasons or [],
        confidence=confidence_score,
        quality=quality_score,
        timestamp=datetime.now(),
        adx=adx,
        rvol=rvol,
        atr_value=atr,
        regime=regime,
        structure_strength=structure_strength,
        entry_details=entry_details,
    )


class TestEvaluator(unittest.TestCase):

    def _assert_rejected(self, result: SignalDecision, err_substr: str):
        self.assertFalse(result.approved, f"Deveria ser REPROVADO, mas foi APROVADO: {result.reject_reason}")
        self.assertIn(err_substr, result.reject_reason.lower())

    def _assert_approved(self, result: SignalDecision):
        self.assertTrue(result.approved, f"Deveria ser APROVADO, mas foi REPROVADO: {result.reject_reason}")

    # --- Caso 1: Entry Zone = FAIL, Consensus = PASS -> REPROVADO ---
    def test_entry_zone_fail_consensus_pass_rejected(self):
        sig = _make_signal(
            entry_score=0.8,
            consensus_score=CONSENSUS_MINIMUM_SCORE + 0.05,
            entry_details=EntryDetails(entry_zone=EntryZone(50100, 49900, 50000, 0.8, "above"),
                score=0.8,
                approved=False,
            ),
        )
        result = DecisionEngine.evaluate_signal(sig, entry_details=sig.entry_details)
        self._assert_rejected(result, "entry zone")
        self.assertFalse(result.entry_zone_ok)

    # --- Caso 2: Consensus = FAIL, Entry Zone = PASS -> REPROVADO ---
    def test_consensus_fail_entry_zone_pass_rejected(self):
        sig = _make_signal(
            entry_score=ENTRY_ZONE_SCORE_MIN + 0.05,
            consensus_score=CONSENSUS_MINIMUM_SCORE - 0.1,
            entry_details=EntryDetails(entry_zone=EntryZone(50100, 49900, 50000, 0.65, "inside"),
                score=0.65,
                approved=True,
            ),
        )
        result = DecisionEngine.evaluate_signal(sig, entry_details=sig.entry_details)
        self._assert_rejected(result, "consensus")
        self.assertFalse(result.consensus_ok)

    # --- Caso 3: Entry Score = 0.40, Entry Zone = FAIL -> REPROVADO ---
    def test_entry_score_pass_entry_zone_fail_rejected(self):
        sig = _make_signal(
            entry_score=0.40,
            entry_details=EntryDetails(entry_zone=EntryZone(50100, 49900, 50000, 0.40, "below"),
                score=0.40,
                approved=False,
            ),
        )
        result = DecisionEngine.evaluate_signal(sig, entry_details=sig.entry_details)
        self._assert_rejected(result, "entry zone")
        self.assertFalse(result.entry_zone_ok)

    # --- Caso 4: Todos os filtros = PASS -> APROVADO ---
    def test_all_filters_pass_approved(self):
        sig = _make_signal(
            quality_score=QUALITY_GATE_MIN_SCORE + 0.1,
            confidence_score=QUALITY_GATE_CONFIDENCE_MIN + 0.1,
            entry_score=ENTRY_ZONE_SCORE_MIN + 0.05,
            consensus_score=CONSENSUS_MINIMUM_SCORE + 0.05,
            risk_score=QUALITY_GATE_RISK_MAX - 0.1,
            entry_details=EntryDetails(entry_zone=EntryZone(50100, 49900, 50000, 0.65, "inside"),
                score=0.65,
                approved=True,
            ),
        )
        result = DecisionEngine.evaluate_signal(sig, entry_details=sig.entry_details)
        self._assert_approved(result)
        self.assertTrue(result.entry_zone_ok)
        self.assertTrue(result.consensus_ok)
        self.assertTrue(result.quality_ok)
        self.assertTrue(result.confidence_ok)
        self.assertTrue(result.risk_ok)

    # --- Caso 5: Trend contraria sem CHoCH/BOS -> REPROVADO ---
    def test_counter_trend_no_confirmation_rejected(self):
        # Contra-tendencia (LONG num regime de downtrend) com BOS mas sem
        # CHoCH — a confirmacao de contra-tendencia exige CHoCH + (BOS ou
        # Liquidity Sweep), entao deve ser reprovado no gate de trend.
        pats = [
            Pattern(type=PatternType.ORDER_BLOCK, direction=SignalDirection.LONG,
                    timeframe="1h", price=50000, confidence=0.8, strength=0.7,
                    description="OB teste", metadata={"upper": 50100, "lower": 49900, "index": 10}),
            Pattern(type=PatternType.BOS, direction=SignalDirection.LONG,
                    timeframe="1h", price=50000, confidence=0.7, strength=0.6,
                    description="BOS teste", metadata={"index": 12}),
        ]
        sig = _make_signal(
            direction=SignalDirection.LONG,
            regime="downtrend",
            structure_strength=0.5,
            patterns=pats,
            entry_details=EntryDetails(entry_zone=EntryZone(50100, 49900, 50000, 0.65, "inside"),
                score=0.65,
                approved=True,
            ),
        )
        result = DecisionEngine.evaluate_signal(sig, entry_details=sig.entry_details)
        self._assert_rejected(result, "trend")

    # --- Caso 6: Contra-tendencia com confirmacao -> APROVADO ---
    def test_counter_trend_with_confirmation_approved(self):
        pats = [
            Pattern(type=PatternType.ORDER_BLOCK, direction=SignalDirection.SHORT,
                    timeframe="1h", price=49500, confidence=0.9, strength=0.8,
                    description="OB forte",
                    metadata={"upper": 49600, "lower": 49400, "index": 10}),
            Pattern(type=PatternType.LIQUIDITY_SWEEP, direction=SignalDirection.SHORT,
                    timeframe="1h", price=51000, confidence=0.8, strength=0.7,
                    description="Sweep", metadata={"index": 8}),
            Pattern(type=PatternType.CHOCH, direction=SignalDirection.SHORT,
                    timeframe="1h", price=49800, confidence=0.8, strength=0.7,
                    description="CHOCH", metadata={"index": 12}),
            Pattern(type=PatternType.BOS, direction=SignalDirection.SHORT,
                    timeframe="1h", price=49700, confidence=0.8, strength=0.7,
                    description="BOS", metadata={"index": 11}),
            Pattern(type=PatternType.FVG, direction=SignalDirection.SHORT,
                    timeframe="1h", price=49600, confidence=0.7, strength=0.6,
                    description="FVG", metadata={"upper": 49650, "lower": 49550, "index": 9}),
        ]
        sig = _make_signal(
            direction=SignalDirection.SHORT,
            regime="uptrend",
            entry_price=49500,
            structure_strength=0.5,
            patterns=pats,
            entry_details=EntryDetails(entry_zone=EntryZone(49600, 49400, 49500, 0.7, "inside"),
                score=0.7, approved=True,
            ),
        )
        result = DecisionEngine.evaluate_signal(sig, entry_details=sig.entry_details)
        self._assert_approved(result)
        self.assertTrue(result.trend_ok)

    # --- Caso adicional: Quality abaixo do minimo ---
    def test_quality_below_min_rejected(self):
        sig = _make_signal(quality_score=QUALITY_GATE_MIN_SCORE - 0.1)
        result = DecisionEngine.evaluate_signal(sig)
        self._assert_rejected(result, "quality")

    # --- Caso adicional: Risk acima do maximo ---
    def test_risk_above_max_rejected(self):
        sig = _make_signal(
            risk_score=QUALITY_GATE_RISK_MAX + 0.1,
            entry_details=EntryDetails(entry_zone=EntryZone(50100, 49900, 50000, 0.65, "inside"),
                score=0.65,
                approved=True,
            ),
        )
        result = DecisionEngine.evaluate_signal(sig, entry_details=sig.entry_details)
        self._assert_rejected(result, "risk")

    # --- Caso adicional: OB ranking seleciona melhor padrao ---
    def test_ob_ranking_selects_best(self):
        from ENGINE.scanner.entry_zone import _rank_pattern
        pats = [
            Pattern(type=PatternType.ORDER_BLOCK, direction=SignalDirection.LONG,
                    timeframe="1h", price=50100.0, confidence=0.3, strength=0.2,
                    description="OB ruim, longe",
                    metadata={"upper": 50200, "lower": 50000, "index": 30}),
            Pattern(type=PatternType.ORDER_BLOCK, direction=SignalDirection.LONG,
                    timeframe="1h", price=49950.0, confidence=0.9, strength=0.8,
                    description="OB bom, perto",
                    metadata={"upper": 50000, "lower": 49900, "index": 5}),
        ]
        ranked = []
        for p in pats:
            score, _ = _rank_pattern(p, 50000.0, 100.0, pats)
            ranked.append((score, p))
        ranked.sort(key=lambda x: x[0], reverse=True)
        best = ranked[0][1]
        self.assertEqual(best.description, "OB bom, perto",
                         "Ranking deveria selecionar OB mais perto com maior confianca")

    # --- ADAUSDT: Entry Zone FAIL + Consensus FAIL -> REPROVADO ---
    def test_adausdt_entry_zone_fail_consensus_fail_rejected(self):
        sig = _make_signal(
            ticker="ADAUSDT",
            direction=SignalDirection.SHORT,
            regime="downtrend",
            entry_score=0.35,
            consensus_score=0.45,
            entry_details=EntryDetails(entry_zone=EntryZone(1.20, 1.10, 1.15, 0.35, "outside"),
                score=0.35,
                approved=False,
            ),
        )
        result = DecisionEngine.evaluate_signal(sig, entry_details=sig.entry_details)
        self.assertFalse(result.approved, "ADAUSDT deve ser REPROVADO: Entry Zone FAIL + Consensus FAIL")
        self.assertFalse(result.entry_zone_ok)
        self.assertFalse(result.consensus_ok)
        self.assertIn("entry", result.reject_reason.lower(),
                      "Primeiro filtro a falhar deve ser Entry Zone")

    # --- ADAUSDT: Entry Zone PASS + Consensus FAIL -> REPROVADO ---
    def test_adausdt_entry_zone_pass_consensus_fail_rejected(self):
        sig = _make_signal(
            ticker="ADAUSDT",
            direction=SignalDirection.SHORT,
            regime="downtrend",
            entry_score=0.55,
            consensus_score=0.45,
            entry_details=EntryDetails(entry_zone=EntryZone(1.20, 1.10, 1.15, 0.55, "inside"),
                score=0.55,
                approved=True,
            ),
        )
        result = DecisionEngine.evaluate_signal(sig, entry_details=sig.entry_details)
        self.assertFalse(result.approved, "ADAUSDT deve ser REPROVADO: Consensus FAIL")
        self.assertTrue(result.entry_zone_ok)
        self.assertFalse(result.consensus_ok)
        self.assertIn("consensus", result.reject_reason.lower(),
                      "Filtro que falha deve ser Consensus")

    # --- ADAUSDT: Todos os filtros PASS -> APROVADO ---
    def test_adausdt_all_pass_approved(self):
        sig = _make_signal(
            ticker="ADAUSDT",
            direction=SignalDirection.SHORT,
            regime="downtrend",
            entry_score=0.55,
            consensus_score=0.65,
            quality_score=0.80,
            confidence_score=0.80,
            risk_score=0.30,
            entry_details=EntryDetails(entry_zone=EntryZone(1.20, 1.10, 1.15, 0.55, "inside"),
                score=0.55,
                approved=True,
            ),
        )
        result = DecisionEngine.evaluate_signal(sig, entry_details=sig.entry_details)
        self.assertTrue(result.approved, "ADAUSDT deve ser APROVADO: todos os filtros OK")
        self.assertTrue(result.entry_zone_ok)
        self.assertTrue(result.consensus_ok)
        self.assertEqual(result.reject_reason, "APROVADO — Todos os filtros institucionais V7")

    # --- Caso: SignalDecision contem todos os campos obrigatorios ---
    def test_decision_result_contains_all_fields(self):
        sig = _make_signal()
        result = DecisionEngine.evaluate_signal(sig)
        d = result.to_dict()
        for field in ("approved", "reject_reason", "quality_ok", "confidence_ok",
                      "risk_ok", "entry_zone_ok", "entry_score_ok", "consensus_ok",
                      "institutional_ok", "trend_ok", "structure_ok", "market_ok",
                      "selected_order_block", "pipeline_hash", "trace_id"):
            self.assertIn(field, d, f"Campo {field} ausente em SignalDecision.to_dict()")


if __name__ == "__main__":
    unittest.main()
