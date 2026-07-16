import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ENGINE.decision.decision_engine import DecisionEngine
from ENGINE.scanner.scanner_types import (
    Signal, ScannerScore, SignalClassification, SignalDirection,
    Pattern, PatternType, MarketStructure, StructureType,
)
from ENGINE.scanner.scanner_config import (
    HARD_MIN_RVOL, HARD_MIN_ADX, CONSENSUS_MINIMUM_SCORE,
)


def _make_signal(**overrides) -> Signal:
    quality = overrides.pop("quality", 0.75)
    confidence = overrides.pop("confidence", 0.80)
    consensus = overrides.pop("consensus", 0.80)
    entry_score = overrides.pop("entry_score", 0.80)
    scores = ScannerScore(entry_score=entry_score, consensus_score=consensus, quality_score=quality)
    bos = Pattern(type=PatternType.BOS, direction=SignalDirection.LONG, timeframe="1h",
                  price=100.0, confidence=0.8, strength=0.8, description="BOS")
    structure = MarketStructure(structure_type=StructureType.UPTREND,
                                swing_highs=[], swing_lows=[], structure_strength=0.6)
    defaults = dict(
        ticker="TESTUSDT", timeframe="1h", direction=SignalDirection.LONG,
        entry_price=100.0, stop_loss=95.0, take_profit_1=110.0, take_profit_2=120.0,
        risk_reward=2.0, scores=scores, classification=SignalClassification.PRATA,
        patterns=[bos], structure=structure, setup="teste", context="teste",
        approval_reasons=[], rejection_reasons=[],
        confidence=confidence, quality=quality,
        rvol=1.0, adx=30.0, regime="trending_up",
        structure_strength=0.6, volume_above_avg=True, structure_valid=True,
        kalman_direction="UP", kalman_trend_state="continuing",
        kalman_confidence=0.8, kalman_tendency=0.5,
    )
    defaults.update(overrides)
    return Signal(**defaults)


def test_rvol_gate_rejects_with_signal_rvol_attribute():
    """Signal tem rvol (float), SignalDecision nao. Testa que o DecisionEngine
    aceita o Signal com rvol no limite."""
    sig = _make_signal(rvol=HARD_MIN_RVOL, adx=30.0, atr_value=1.0)
    sd = DecisionEngine.evaluate_signal(sig)
    assert sd.rvol_ok is True, f"RVOL {HARD_MIN_RVOL} deveria passar"


def test_rvol_gate_rejects_below_threshold():
    """RVOL abaixo do threshold deve rejeitar sem AttributeError."""
    sig = _make_signal(rvol=HARD_MIN_RVOL * 0.5, adx=30.0)
    sd = DecisionEngine.evaluate_signal(sig)
    assert sd.approved is False
    assert "RVOL" in (sd.reject_reason or "")
    assert sd.rvol_ok is False


def test_adx_gate_rejects_below_threshold():
    """ADX abaixo do threshold deve rejeitar sem AttributeError."""
    sig = _make_signal(rvol=1.0, adx=HARD_MIN_ADX * 0.5)
    sd = DecisionEngine.evaluate_signal(sig)
    assert sd.approved is False
    assert "ADX" in (sd.reject_reason or "")
    assert sd.adx_ok is False


def test_rvol_attribute_not_needed_on_signal_decision():
    """SignalDecision NAO tem atributo rvol/ADX — isso e esperado,
    o Signal e quem carrega esses valores."""
    sig = _make_signal(rvol=0.3, adx=15.0)
    sd = DecisionEngine.evaluate_signal(sig)
    assert not hasattr(sd, 'rvol'), "SignalDecision nao deveria ter .rvol"
    assert not hasattr(sd, 'adx'), "SignalDecision nao deveria ter .adx"
    assert hasattr(sd, 'rvol_ok'), "SignalDecision deveria ter .rvol_ok"
    assert hasattr(sd, 'adx_ok'), "SignalDecision deveria ter .adx_ok"
    assert sd.rvol_ok is False
    assert sd.adx_ok is None  # ADX gate nunca rodou


def test_consensus_gate_uses_config_threshold():
    """Consensus usa CONSENSUS_MINIMUM_SCORE do config."""
    sig = _make_signal(rvol=1.0, adx=30.0, consensus=CONSENSUS_MINIMUM_SCORE * 0.9,
                       structure_strength=0.6, entry_score=0.8)
    sd = DecisionEngine.evaluate_signal(sig)
    assert sd.approved is False
    assert "Consensus" in (sd.reject_reason or "")


def test_full_approval_with_new_thresholds():
    """Sinal forte passa com os thresholds recalibrados."""
    sig = _make_signal(rvol=HARD_MIN_RVOL + 0.1, adx=HARD_MIN_ADX + 5,
                       consensus=CONSENSUS_MINIMUM_SCORE + 0.1,
                       entry_score=0.8, quality=0.75, confidence=0.80,
                       atr_value=1.0)
    sd = DecisionEngine.evaluate_signal(sig)
    assert sd.approved, f"Sinal forte deveria passar: {sd.reject_reason}"
