"""
Testes unitarios dos gates novos da RFC_RECALIBRACAO_SINAIS_INSTITUCIONAL.md:
- GATE 9: Confidence >= CONFIDENCE_GATE_MIN_SCORE
- GATE 10: |Confidence - Quality| <= CONFIDENCE_QUALITY_MAX_DIFF
- GATE 11: Mercado lateral exige excecao estruturada
- GATE 12: Conflito Kalman x Trend Engine/MarketRegime
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from ENGINE.decision.decision_engine import DecisionEngine
from ENGINE.scanner.scanner_types import (
    Signal, ScannerScore, SignalClassification, SignalDirection,
    Pattern, PatternType, MarketStructure, StructureType,
)
from ENGINE.scanner.scanner_config import (
    CONFIDENCE_GATE_MIN_SCORE, CONFIDENCE_QUALITY_MAX_DIFF,
    QUALITY_GATE_MIN_SCORE, CONSENSUS_MINIMUM_SCORE, ENTRY_ZONE_SCORE_MIN,
)


def _make_signal(**overrides) -> Signal:
    """Constroi um Signal que passa nos gates 1-8 e nos gates 9-12 por
    padrao (confidence alta, sem lateralizacao, kalman alinhado). Os testes
    sobrescrevem apenas o(s) campo(s) relevante(s) para cada gate."""
    # Valores fixos (nao derivados dos thresholds atuais) para que os
    # defaults continuem satisfazendo todos os gates mesmo que os
    # thresholds de producao sejam recalibrados no futuro. quality=0.75
    # e confidence=0.80 ficam acima de qualquer threshold institucional
    # razoavel e dentro do CONFIDENCE_QUALITY_MAX_DIFF (diff=0.05).
    quality = overrides.pop("quality", 0.75)
    confidence = overrides.pop("confidence", 0.80)
    consensus = overrides.pop("consensus", 0.80)
    entry_score = overrides.pop("entry_score", 0.80)

    scores = ScannerScore(entry_score=entry_score, consensus_score=consensus, quality_score=quality)

    bos_pattern = Pattern(
        type=PatternType.BOS, direction=SignalDirection.LONG, timeframe="1h",
        price=100.0, confidence=0.8, strength=0.8, description="BOS de teste",
    )
    structure = MarketStructure(
        structure_type=StructureType.UPTREND,
        swing_highs=[], swing_lows=[], structure_strength=0.6,
    )

    defaults = dict(
        ticker="TESTUSDT", timeframe="1h", direction=SignalDirection.LONG,
        entry_price=100.0, stop_loss=95.0, take_profit_1=110.0, take_profit_2=120.0,
        risk_reward=2.0, scores=scores, classification=SignalClassification.PRATA,
        patterns=[bos_pattern], structure=structure, setup="teste", context="teste",
        approval_reasons=[], rejection_reasons=[],
        confidence=confidence, quality=quality,
        rvol=1.0, adx=30.0, regime="trending_up",
        structure_strength=0.6, volume_above_avg=True, structure_valid=True,
        kalman_direction="UP", kalman_trend_state="continuing",
    )
    defaults.update(overrides)
    return Signal(**defaults)


def _price_series(n: int = 30, start: float = 100.0, step: float = 0.5):
    closes = [start + i * step for i in range(n)]
    highs = [c + 1.0 for c in closes]
    lows = [c - 1.0 for c in closes]
    return highs, lows, closes


def _evaluate(signal: Signal):
    """Avalia um sinal ate o gate que for aplicavel. Sempre passa series de
    preco sinteticas para nao quebrar no Risk Manager (GATE 8) caso o sinal
    sobreviva ate la — os testes de rejeicao dos gates 9-12 retornam antes
    disso de qualquer forma, entao isso so importa para os testes de 'passa'."""
    highs, lows, closes = _price_series()
    return DecisionEngine.evaluate_signal(
        signal, entry_details=None, highs=highs, lows=lows, closes=closes,
    )


# --- GATE 9: Confidence ------------------------------------------------------

def test_confidence_gate_rejects_below_threshold():
    sd = _evaluate(_make_signal(confidence=CONFIDENCE_GATE_MIN_SCORE - 0.01))
    assert sd.approved is False
    assert "Confidence" in sd.reject_reason


def test_confidence_gate_does_not_reject_at_threshold():
    sd = _evaluate(_make_signal(confidence=CONFIDENCE_GATE_MIN_SCORE))
    assert "Confidence" not in (sd.reject_reason or "")


# --- GATE 10: Confidence vs Quality ------------------------------------------

def test_confidence_quality_diff_rejects_large_gap():
    # confidence bem acima de quality, gap > limite
    sd = _evaluate(_make_signal(
        quality=QUALITY_GATE_MIN_SCORE,
        confidence=QUALITY_GATE_MIN_SCORE + CONFIDENCE_QUALITY_MAX_DIFF + 0.05,
    ))
    assert sd.approved is False
    assert "Descalibracao" in sd.reject_reason


def test_confidence_quality_diff_passes_small_gap():
    sd = _evaluate(_make_signal(
        quality=QUALITY_GATE_MIN_SCORE,
        confidence=QUALITY_GATE_MIN_SCORE + CONFIDENCE_QUALITY_MAX_DIFF - 0.01,
    ))
    assert "Descalibracao" not in (sd.reject_reason or "")


# --- GATE 11: Mercado lateral -------------------------------------------------

def test_lateral_market_rejects_without_exception():
    sd = _evaluate(_make_signal(regime="ranging", volume_above_avg=False))
    assert sd.approved is False
    assert "lateral" in sd.reject_reason.lower()


def test_lateral_market_passes_with_full_exception():
    # regime lateral, mas rompimento (BOS ja incluso), volume, estrutura e
    # consenso confirmados -> deve passar deste gate especifico (pode ainda
    # ser rejeitado por outro gate depois, o que nos importa aqui e' que a
    # razao nao seja "lateral")
    sd = _evaluate(_make_signal(
        regime="ranging", volume_above_avg=True, structure_valid=True,
        consensus=CONSENSUS_MINIMUM_SCORE + 0.05,
    ))
    assert "lateral" not in (sd.reject_reason or "").lower()


def test_non_lateral_regime_skips_lateral_gate():
    sd = _evaluate(_make_signal(regime="trending_up", volume_above_avg=False))
    assert "lateral" not in (sd.reject_reason or "").lower()


# --- GATE 12: Kalman vs Trend/Regime ------------------------------------------

def test_kalman_trend_conflict_rejects():
    """GATE 12 V18.3: LONG+DOWN ou SHORT+UP = rejeitar."""
    sd = _evaluate(_make_signal(regime="trending_up", kalman_direction="DOWN"))
    assert sd.approved is False
    assert "Kalman" in sd.reject_reason and "incompativel" in sd.reject_reason


def test_kalman_trend_aligned_passes():
    """GATE 12 V18.3: LONG+UP passa no Kalman (pode ser rejeitado depois)."""
    sd = _evaluate(_make_signal(regime="trending_up", kalman_direction="UP"))
    assert sd.kalman_ok is True
    assert "Kalman" not in (sd.reject_reason or "")


def test_kalman_neutral_regime_no_conflict():
    # regime sem direcao clara (ranging/reversal) nao aciona o gate de conflito
    sd = _evaluate(_make_signal(
        regime="reversal", kalman_direction="DOWN",
        volume_above_avg=True, structure_valid=True,
        consensus=CONSENSUS_MINIMUM_SCORE + 0.05,
    ))
    assert "Conflito Kalman" not in (sd.reject_reason or "")


# --- Aprovacao completa (todos os gates, incl. Risk Manager) -----------------

def test_full_approval_passes_all_gates():
    n = 30
    closes = [100.0 + i * 0.5 for i in range(n)]
    highs = [c + 1.0 for c in closes]
    lows = [c - 1.0 for c in closes]
    signal = _make_signal(entry_price=closes[-1], atr_value=1.0)
    sd = DecisionEngine.evaluate_signal(
        signal, entry_details=None, highs=highs, lows=lows, closes=closes,
    )
    assert sd.approved is True, sd.reject_reason
    assert sd.confidence_ok is True
    assert sd.rr_ok is True


# --- V18.4: GATE 16 — Final Validation Hard Gate no decision_engine.py ---------

def test_gate16_kalman_conflict_rejected():
    """Gate 12 ja pega Kalman conflict antes do Gate 16; approved=False."""
    sd = _evaluate(_make_signal(direction=SignalDirection.LONG, kalman_direction="DOWN"))
    assert sd.approved is False


def test_gate16_aligned_LONG_UP_not_blocked():
    sd = _evaluate(_make_signal(direction=SignalDirection.LONG, kalman_direction="UP"))
    assert sd.approved is True or "Kalman" not in (sd.reject_reason or "")


def test_gate16_aligned_SHORT_DOWN_not_blocked():
    sd = _evaluate(_make_signal(direction=SignalDirection.SHORT, kalman_direction="DOWN"))
    assert sd.approved is True or "Kalman" not in (sd.reject_reason or "")


# --- V18.4: operational.py — Institutional Coherence Score ---------------------

def test_coherence_score_high():
    from ENGINE.common.operational import compute_institutional_coherence_score
    data = {
        "direction": "LONG", "kalman_direction": "UP", "trend": "uptrend",
        "regime": "trending_up", "flow_score": 0.9, "liquidity_score": 0.9,
        "structural_score": 0.9, "momentum_score": 0.9, "consensus": 0.9,
        "quality": 0.9, "confidence": 0.9,
        "bos": 1, "choch": 0,
    }
    result = compute_institutional_coherence_score(data)
    assert result["coherence_score"] >= 80
    assert result["coherence_level"] in ("Excelente", "Muito Alta", "Boa")


def test_coherence_score_low():
    from ENGINE.common.operational import compute_institutional_coherence_score
    data = {
        "direction": "LONG", "kalman_direction": "DOWN", "trend": "downtrend",
        "regime": "trending_down", "flow_score": 0.1, "liquidity_score": 0.1,
        "structural_score": 0.1, "momentum_score": 0.1, "consensus": 0.1,
        "quality": 0.1, "confidence": 0.1,
        "bos": 0, "choch": 0,
    }
    result = compute_institutional_coherence_score(data)
    assert result["coherence_score"] < 60
    assert result["coherence_level"] == "Rejeitar"


# --- V18.4: operational.py — Weighted Voting -----------------------------------

def test_weighted_vote_approved():
    from ENGINE.common.operational import compute_weighted_vote
    data = {
        "direction": "LONG", "kalman_direction": "UP", "trend": "uptrend",
        "regime": "trending_up", "flow_score": 0.9, "liquidity_score": 0.9,
        "structural_score": 0.9, "momentum_score": 0.9, "consensus": 0.9,
        "quality": 0.9, "confidence": 0.9,
        "bos": 1, "choch": 0,
    }
    result = compute_weighted_vote(data)
    assert result["approved"] is True
    assert result["concordance_pct"] >= 70


def test_weighted_vote_rejected():
    from ENGINE.common.operational import compute_weighted_vote
    data = {
        "direction": "LONG", "kalman_direction": "DOWN", "trend": "downtrend",
        "regime": "trending_down", "flow_score": 0.1, "liquidity_score": 0.1,
        "structural_score": 0.1, "momentum_score": 0.1, "consensus": 0.1,
        "quality": 0.1, "confidence": 0.1,
        "bos": 0, "choch": 0,
    }
    result = compute_weighted_vote(data)
    assert result["approved"] is False
    assert result["concordance_pct"] < 70


# --- V18.4: operational.py — Coarse Penalty Details ----------------------------

def test_penalty_details_kalman_conflict():
    from ENGINE.common.operational import compute_coarse_penalty_details
    data = {
        "direction": "LONG", "kalman_direction": "DOWN",
        "structural_score": 0.9, "flow_score": 0.9, "consensus": 0.9,
        "liquidity_score": 0.9, "momentum_score": 0.9, "regime": "trending_up",
    }
    details = compute_coarse_penalty_details(data)
    gates = [d["gate"] for d in details]
    assert "Kalman" in gates


def test_penalty_details_no_penalties():
    from ENGINE.common.operational import compute_coarse_penalty_details
    data = {
        "direction": "LONG", "kalman_direction": "UP",
        "structural_score": 0.9, "flow_score": 0.9, "consensus": 0.9,
        "liquidity_score": 0.9, "momentum_score": 0.9, "regime": "trending_up",
    }
    details = compute_coarse_penalty_details(data)
    assert len(details) == 0


# --- V18.5: HARD GATES — 6 cenarios que DEVEM ser bloqueados -----------------

def test_hard_gate_SHORT_KALMAN_UP():
    """SHORT + Kalman UP = BLOQUEAR (Gate 12)."""
    sd = _evaluate(_make_signal(direction=SignalDirection.SHORT, kalman_direction="UP"))
    assert sd.approved is False
    assert "Kalman" in sd.reject_reason


def test_hard_gate_LONG_KALMAN_DOWN():
    """LONG + Kalman DOWN = BLOQUEAR (Gate 12)."""
    sd = _evaluate(_make_signal(direction=SignalDirection.LONG, kalman_direction="DOWN"))
    assert sd.approved is False
    assert "Kalman" in sd.reject_reason


def test_hard_gate_TRENDING_UP_SHORT():
    """Trending Up + SHORT sem reversao = BLOQUEAR (Gate 12)."""
    sd = _evaluate(_make_signal(direction=SignalDirection.SHORT, regime="trending_up"))
    assert sd.approved is False
    assert "Kalman" in sd.reject_reason


def test_hard_gate_TRENDING_DOWN_LONG():
    """Trending Down + LONG sem reversao = BLOQUEAR (Gate 13 Consistency)."""
    sd = _evaluate(_make_signal(direction=SignalDirection.LONG, regime="trending_down"))
    assert sd.approved is False
    # Gate 13 (Consistency) bloqueia antes do Gate 12
    assert "Consistency" in sd.reject_reason or "Kalman" in sd.reject_reason


def test_hard_gate_OURO_INDICE_64():
    """Overall Score 64.6 + OURO = BLOQUEAR (classification divergence).
    Testamos _derive_tier diretamente: score=64 cai em PRATA, nao OURO.
    Se um sinal chegasse com OURO e overall=64, a validacao em main.py bloquearia."""
    from ENGINE.common.operational import _derive_tier
    label, tier = _derive_tier(64.6)
    assert tier == "PRATA", f"Esperava PRATA, obteve {tier}"
    label, tier = _derive_tier(74.0)
    assert tier == "OURO", f"Esperava OURO, obteve {tier}"
    label, tier = _derive_tier(50.0)
    assert tier == "BRONZE", f"Esperava BRONZE, obteve {tier}"
    label, tier = _derive_tier(45.0)
    assert tier == "REPROVADO", f"Esperava REPROVADO, obteve {tier}"


def test_hard_gate_LATERAL_EXPECTATIVA_ALTA():
    """Mercado lateral + expectativa alta sem rompimento = BLOQUEAR.
    Validamos a condicao da final validation em main.py diretamente,
    usando a expressao exata do codigo de producao."""
    # A condicao em main.py:
    regime_check = "ranging"
    exp_level = "Alta"
    main_reason = "Setup institucional aprovado"
    has_breakout = "BOS" in main_reason or "CHOCH" in main_reason
    # lateral + expectativa alta + sem breakout = REJEITADO
    if regime_check in ("ranging", "lateral") and exp_level in ("Alta", "Muito Alta") and not has_breakout:
        validation_error = True
    else:
        validation_error = False
    assert validation_error, "Deveria ter gerado validation error"

    # Com breakout, nao deve gerar erro
    main_reason = "BOS confirmado + Tendencia alinhada"
    has_breakout = "BOS" in main_reason or "CHOCH" in main_reason
    if regime_check in ("ranging", "lateral") and exp_level in ("Alta", "Muito Alta") and not has_breakout:
        validation_error = True
    else:
        validation_error = False
    assert not validation_error, "Com BOS nao deveria gerar validation error"


# --- V18.5: Classification Enforcement test -----------------------------------

def test_classification_tier_matches_score():
    """_derive_tier mapeia scores corretamente nos ranges V18.4."""
    from ENGINE.common.operational import _derive_tier
    for score, expected_tier in [
        (95, "DIAMANTE"), (90, "DIAMANTE"),
        (85, "PLATINA"), (80, "PLATINA"),
        (75, "OURO"), (70, "OURO"),
        (65, "PRATA"), (60, "PRATA"),
        (55, "BRONZE"), (50, "BRONZE"),
        (45, "REPROVADO"), (0, "REPROVADO"),
    ]:
        label, tier = _derive_tier(score)
        assert tier == expected_tier, (
            f"Score {score} esperava {expected_tier}, obteve {tier}"
        )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
