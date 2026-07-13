"""
Testes unitarios da reescala de componentes do quality_score
(RFC_RECALIBRACAO_SINAIS_INSTITUCIONAL.md) — flow_score, structural_score,
risk_score e conviction_score tinham teto real observado bem abaixo de 1.0
(ate 0.71), o que limitava quality_score a ~0.65 mesmo para o melhor setup
possivel. rescale_to_ceiling() estica esse teto real para 1.0.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ENGINE.scanner.scanner_scoring import rescale_to_ceiling, compute_quality_score, score_institutional
from ENGINE.scanner.scanner_config import QUALITY_COMPONENT_CEILINGS
from ENGINE.scanner.scanner_types import ScannerScore


def test_rescale_at_ceiling_returns_one():
    for component, ceiling in QUALITY_COMPONENT_CEILINGS.items():
        assert rescale_to_ceiling(ceiling, component) == 1.0


def test_rescale_above_ceiling_clamps_to_one():
    for component, ceiling in QUALITY_COMPONENT_CEILINGS.items():
        assert rescale_to_ceiling(ceiling * 2, component) == 1.0


def test_rescale_zero_stays_zero():
    for component in QUALITY_COMPONENT_CEILINGS:
        assert rescale_to_ceiling(0.0, component) == 0.0


def test_rescale_component_without_ceiling_passes_through():
    assert rescale_to_ceiling(0.42, "liquidity_score") == 0.42
    assert rescale_to_ceiling(0.9, "entry_score") == 0.9


def test_quality_score_reaches_90_plus_for_best_observed_setup():
    """Composto com o melhor valor real ja observado (p99) em cada
    componente (ver RFC) — deve entrar na faixa 'Excelente' (90-100)."""
    struct_s = rescale_to_ceiling(0.6183, "structural_score")
    risk_s = rescale_to_ceiling(0.5694, "risk_score")
    flow_s = rescale_to_ceiling(0.50, "flow_score")
    conv_s = rescale_to_ceiling(0.6705, "conviction_score")
    inst_s = score_institutional(struct_s, 0.909, 0.940, 1.000, risk_s, 0.886, flow_s)
    scores = ScannerScore(
        institutional_score=inst_s, structural_score=struct_s, market_score=0.909,
        momentum_score=0.940, liquidity_score=1.000, risk_score=risk_s,
        confidence_score=0.886, flow_score=flow_s, timing_index=0.980,
        conviction_score=conv_s, entry_score=1.000,
    )
    q = compute_quality_score(scores)
    assert q >= 0.90, f"esperava quality_score >= 0.90 para o melhor setup observado, obteve {q}"


def test_quality_score_typical_setup_stays_below_60():
    """Composto com as medias reais observadas — nao deve ser inflado
    artificialmente para a faixa 'Boa'/'Excelente'."""
    struct_s = rescale_to_ceiling(0.279, "structural_score")
    risk_s = rescale_to_ceiling(0.382, "risk_score")
    flow_s = rescale_to_ceiling(0.250, "flow_score")
    conv_s = rescale_to_ceiling(0.465, "conviction_score")
    inst_s = score_institutional(struct_s, 0.499, 0.522, 0.875, risk_s, 0.716, flow_s)
    scores = ScannerScore(
        institutional_score=inst_s, structural_score=struct_s, market_score=0.499,
        momentum_score=0.522, liquidity_score=0.875, risk_score=risk_s,
        confidence_score=0.716, flow_score=flow_s, timing_index=0.585,
        conviction_score=conv_s, entry_score=0.261,
    )
    q = compute_quality_score(scores)
    assert q < 0.60, f"esperava quality_score < 0.60 para um setup mediano tipico, obteve {q}"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
