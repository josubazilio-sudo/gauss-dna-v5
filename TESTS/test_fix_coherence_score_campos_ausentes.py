"""Bug fix — Coherence Score / Votacao Ponderada liam campos ausentes.

Ver RFC_FIX_COHERENCE_SCORE_CAMPOS_AUSENTES.md. Reproduz exatamente o
cenario real (CHZUSDT SHORT em regime trending_down, bem alinhado) antes
e depois da correcao.
"""
from ENGINE.common.operational import (
    compute_institutional_coherence_score, compute_weighted_vote,
)
from ENGINE.decision.signal_decision import SignalDecision


def _aligned_short_trending_down_signal():
    """Sinal SHORT genuinamente bem alinhado: kalman down, tendencia
    trending_down (formato real do MarketRegime), estrutura/liquidez/
    fluxo/momentum fortes, com BOS confirmado."""
    return {
        "direction": "SHORT",
        "kalman_direction": "DOWN",
        "trend": "Trending_Down",  # formato real: str(MarketRegime.TRENDING_DOWN).title()
        "regime": "trending_down",
        "flow_score": 0.65,
        "liquidity_score": 0.70,
        "structural_score": 0.75,
        "momentum_score": 0.60,
        "consensus_score": 0.75,
        "quality_score": 0.73,
        "confidence_score": 0.80,
        "bos": 1,
        "choch": 0,
    }


def test_signal_decision_to_dict_now_exports_flow_and_momentum_score():
    sd = SignalDecision(flow_score=0.5, momentum_score=0.6)
    d = sd.to_dict()
    assert d["flow_score"] == 0.5
    assert d["momentum_score"] == 0.6


def test_coherence_score_recognizes_bos_via_counter_not_missing_patterns_key():
    data = _aligned_short_trending_down_signal()
    result = compute_institutional_coherence_score(data)
    assert result["modules"]["padrao"] == 100.0  # bos=1 -> pattern_ok


def test_coherence_score_recognizes_trending_down_regime_alignment():
    data = _aligned_short_trending_down_signal()
    result = compute_institutional_coherence_score(data)
    assert result["modules"]["regime"] == 100.0  # SHORT bem alinhado com trending_down


def test_coherence_score_reads_flow_and_momentum_correctly():
    data = _aligned_short_trending_down_signal()
    result = compute_institutional_coherence_score(data)
    assert result["modules"]["fluxo"] == 100.0  # flow_score 0.65 >= 0.3
    assert result["modules"]["momentum"] == 100.0  # momentum_score 0.60 >= 0.5


def test_coherence_score_well_aligned_signal_scores_high_after_fix():
    """Antes do fix, este exato sinal (bem alinhado na realidade) ficava
    preso em ~56 pontos por causa dos 4 componentes zerados
    incorretamente. Apos o fix, deve pontuar bem mais alto."""
    data = _aligned_short_trending_down_signal()
    result = compute_institutional_coherence_score(data)
    assert result["coherence_score"] > 80.0


def test_weighted_vote_regression_reproduces_old_bug_score_without_fields():
    """Sem bos/choch/flow_score/momentum_score/trend no formato certo,
    o sinal deve pontuar baixo (mantendo o comportamento correto de
    'sem dados = nao aprovar')."""
    minimal_data = {
        "direction": "SHORT",
        "kalman_direction": "DOWN",
        "trend": "Trending_Down",
        "quality_score": 0.73,
        "confidence_score": 0.80,
        "consensus_score": 0.75,
        # sem flow_score/momentum_score/bos/choch -> devem ser tratados
        # como ausentes (0), nao mascarados como presentes
    }
    result = compute_weighted_vote(minimal_data)
    assert result["votes"]["fluxo"] is False  # flow_score ausente -> 0 -> nao vota sim
    assert result["votes"]["padrao"] is False  # sem bos/choch


def test_weighted_vote_approves_well_aligned_trending_signal_after_fix():
    data = _aligned_short_trending_down_signal()
    result = compute_weighted_vote(data)
    assert result["votes"]["regime"] is True
    assert result["votes"]["padrao"] is True
    assert result["approved"] is True


def test_weighted_vote_regime_check_matches_real_marketregime_values():
    """MarketRegime.TRENDING_UP/TRENDING_DOWN (ENGINE/market/market_types.py)
    -- garante que o fix cobre ambas as direcoes."""
    long_uptrend = {
        "direction": "LONG", "kalman_direction": "UP", "trend": "Trending_Up",
        "quality_score": 0.7, "confidence_score": 0.7, "consensus_score": 0.7,
        "flow_score": 0.5, "momentum_score": 0.5, "liquidity_score": 0.7,
        "structural_score": 0.7, "bos": 1, "choch": 0,
    }
    result = compute_weighted_vote(long_uptrend)
    assert result["votes"]["regime"] is True


def test_coherence_score_ranging_regime_still_gets_partial_credit():
    """Regressao: mercado 'ranging' deve continuar recebendo credito
    parcial (0.5), comportamento que ja funcionava antes do fix."""
    data = _aligned_short_trending_down_signal()
    data["trend"] = "Ranging"
    result = compute_institutional_coherence_score(data)
    assert result["modules"]["regime"] == 50.0
