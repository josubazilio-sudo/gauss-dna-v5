import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ENGINE.decision.decision_engine import DecisionEngine
from ENGINE.scanner.scanner_types import (
    Signal, ScannerScore, SignalClassification, SignalDirection,
    Pattern, PatternType, MarketStructure, StructureType, EntryZone, EntryDetails,
)


def _score():
    return ScannerScore(
        institutional_score=0.90, structural_score=0.90,
        market_score=0.90, momentum_score=0.90,
        liquidity_score=0.90, risk_score=0.20,
        confidence_score=0.90, quality_score=0.90,
        entry_score=0.90, consensus_score=0.90,
        conviction_score=0.90, flow_score=0.90,
        timing_index=0.90,
    )


def _signal(rvol=2.0):
    scores = _score()
    structure = MarketStructure(
        structure_type=StructureType.UPTREND,
        swing_highs=[], swing_lows=[],
        structure_strength=0.80,
    )
    patterns = [
        Pattern(PatternType.BOS, SignalDirection.LONG, "1h", 100.0, 0.90, 0.80, "BOS"),
        Pattern(PatternType.ORDER_BLOCK, SignalDirection.LONG, "1h", 99.0, 0.90, 0.80, "OB", {"upper": 100.0, "lower": 98.0, "index": 10}),
    ]
    entry_details = EntryDetails(EntryZone(100.0, 98.0, 99.0, 0.90, "inside"), 0.90, True, True)
    entry_details.spread = 0.0
    return Signal(
        ticker="BTCUSDT", timeframe="1h",
        direction=SignalDirection.LONG,
        entry_price=100.0, stop_loss=98.0,
        take_profit_1=104.0, take_profit_2=108.0,
        risk_reward=2.0,
        scores=scores, classification=SignalClassification.OURO,
        patterns=patterns, structure=structure,
        setup="test", context="test",
        approval_reasons=[], rejection_reasons=[],
        confidence=0.90, quality=0.90,
        rvol=rvol, adx=40.0, atr_value=1.0,
        regime="trending_up", entry_details=entry_details,
        structure_strength=0.80,
    )


class TestGateResultsFidelity(unittest.TestCase):
    """Regressao: sd.<gate>_ok tinha default bool=False, entao um gate que
    NUNCA rodava (porque evaluate_signal() ja retornou num gate anterior)
    aparecia no TRACE[...] GateResults identico a um gate que rodou e
    reprovou de verdade — dando a falsa impressao de que 12+ sistemas
    reprovaram o sinal quando apenas 1 (ex.: RVOL) realmente rodou. Agora
    o default e None ('nao avaliado'), distinto de False ('avaliado e
    reprovado')."""

    def test_gate_that_never_ran_is_none_not_false(self):
        sig = _signal(rvol=0.3)  # reprova no GATE 3 (RVOL < 1.0), logo no inicio
        sd = DecisionEngine.evaluate_signal(sig, entry_details=sig.entry_details)

        self.assertIn("RVOL", sd.reject_reason)
        self.assertFalse(sd.approved)
        # Gates posteriores ao RVOL nunca rodaram — devem ser None, nao False
        self.assertIsNone(sd.consensus_ok)
        self.assertIsNone(sd.quality_ok)
        self.assertIsNone(sd.entry_zone_ok)
        self.assertIsNone(sd.institutional_ok)

    def test_gate_that_actually_fails_is_false_not_none(self):
        sig = _signal(rvol=2.0)  # passa RVOL/ADX/spread/BOS, mas pode falhar depois
        sd = DecisionEngine.evaluate_signal(
            sig, entry_details=sig.entry_details,
            highs=[101.0] * 20, lows=[99.0] * 20, closes=[100.0] * 20,
        )
        # Independente do resultado final, os gates que efetivamente rodaram
        # (RVOL/ADX, testados antes deste ponto) devem estar marcados True,
        # nunca None, ja que sabemos que o fluxo passou por eles.
        self.assertTrue(sd.rvol_ok)
        self.assertTrue(sd.adx_ok)

    def test_all_truthiness_semantics_unchanged(self):
        """None e False sao ambos falsy — all([...]) usado em
        main.py._decision_has_required_flags nao muda de comportamento."""
        sig = _signal(rvol=0.3)
        sd = DecisionEngine.evaluate_signal(sig, entry_details=sig.entry_details)
        required = [
            sd.market_ok, sd.trend_ok, sd.structure_ok, sd.entry_zone_ok,
            sd.entry_score_ok, sd.consensus_ok, sd.quality_ok,
            sd.confidence_ok, sd.risk_ok, sd.institutional_ok,
            sd.rvol_ok, sd.adx_ok, sd.flow_ok, sd.timing_ok,
            sd.liquidity_ok, sd.structural_ok, sd.conviction_ok, sd.rr_ok,
        ]
        self.assertFalse(all(required))


if __name__ == "__main__":
    unittest.main()
