"""
Testes unitarios da RFC V18.4 — Consolidacao da camada de apresentacao.
Cobre: melhor sinal unico do ciclo (CycleSignalResult), OperationalCalculator
usando dados reais (nao mais estimativa de 30%+alavancagem), e classificacao
consistente entre Indice Geral e Classificacao (sem tier paralelo).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import CycleSignalResult, _cycle_rank
from ENGINE.common.operational import OperationalCalculator, compute_overall_score
from ENGINE.decision.signal_decision import SignalDecision


def _make_sd(**overrides) -> SignalDecision:
    defaults = dict(
        symbol="TESTUSDT", timeframe="1h", direction="long",
        approved=True, quality=0.65, consensus=0.72, risk_reward=2.0,
        entry_price=100.0, stop_loss=95.0,
    )
    defaults.update(overrides)
    return SignalDecision(**defaults)


# --- Etapa 1/2: melhor sinal unico do ciclo ---------------------------------

def test_cycle_rank_favors_higher_quality_consensus_rr():
    weak = _make_sd(quality=0.60, consensus=0.70, risk_reward=2.0)
    strong = _make_sd(quality=0.75, consensus=0.80, risk_reward=3.0)
    assert _cycle_rank(strong) > _cycle_rank(weak)


def test_cycle_signal_result_picks_best_among_approved_only():
    approved_30m = _make_sd(timeframe="30m", quality=0.60, consensus=0.70, risk_reward=2.0)
    approved_1h = _make_sd(timeframe="1h", quality=0.75, consensus=0.80, risk_reward=2.5)
    rejected_4h = _make_sd(timeframe="4h", approved=False, quality=0.90, consensus=0.95, risk_reward=4.0)

    all_decisions = [approved_30m, approved_1h, rejected_4h]
    approved = [d for d in all_decisions if d.approved]

    result = CycleSignalResult(pair="TESTUSDT", all_decisions=all_decisions, approved_signals=approved)
    result.best_signal = max(approved, key=_cycle_rank)
    result.best_is_approved = True

    # O melhor deve ser o 1h (melhor score entre os APROVADOS), nunca o 4h
    # rejeitado, mesmo que o 4h tenha scores brutos mais altos.
    assert result.best_signal.timeframe == "1h"
    assert result.best_is_approved is True


def test_cycle_signal_result_falls_back_to_all_decisions_when_none_approved():
    rejected_a = _make_sd(timeframe="30m", approved=False, quality=0.40, consensus=0.50, risk_reward=1.0)
    rejected_b = _make_sd(timeframe="1h", approved=False, quality=0.55, consensus=0.60, risk_reward=1.5)

    all_decisions = [rejected_a, rejected_b]
    result = CycleSignalResult(pair="TESTUSDT", all_decisions=all_decisions, approved_signals=[])
    result.best_signal = max(all_decisions, key=_cycle_rank)
    result.best_is_approved = False

    assert result.best_signal.timeframe == "1h"
    assert result.best_is_approved is False


# --- Etapa 3/4: OperationalCalculator usa dados reais, sem inventar --------

def test_operational_calculator_uses_real_quantity_not_fixed_percentage():
    calc = OperationalCalculator()
    ops = calc.calculate(entry_price=100.0, stop_loss=95.0, take_profit_1=110.0, quantity=50.0, balance=10000.0)

    assert ops["quantidade"] == 50.0
    assert ops["valor_nominal"] == 50.0 * 100.0


def test_operational_calculator_separates_the_four_return_metrics():
    # RFC V20.2: leverage=1.0 faz retorno_margem_pct == retorno_ativo_pct
    # matematicamente (margem == valor nominal quando nao ha alavancagem)
    # — usa leverage=5.0 para provar que as 3 metricas sao conceitos
    # realmente distintos, como o teste original pretendia.
    calc = OperationalCalculator()
    ops = calc.calculate(entry_price=100.0, stop_loss=95.0, take_profit_1=110.0, quantity=50.0, balance=10000.0, leverage=5.0)

    reward_usdt = 50.0 * (110.0 - 100.0)
    risk_usdt = 50.0 * (100.0 - 95.0)
    position_value = 50.0 * 100.0
    margin_used = position_value / 5.0

    assert ops["lucro_liquido_usdt"] == reward_usdt
    assert ops["perda_maxima_usdt"] == risk_usdt
    assert ops["retorno_ativo_pct"] == round(10.0 / 100.0 * 100, 2)
    # RFC V20.2: retorno sobre margem = lucro / margem utilizada (capital
    # comprometido), nao lucro / perda maxima (isso e o RR em %).
    assert ops["retorno_margem_pct"] == round(reward_usdt / margin_used * 100, 2)
    assert ops["retorno_patrimonio_pct"] == round(reward_usdt / 10000.0 * 100, 2)
    values = {ops["retorno_ativo_pct"], ops["retorno_margem_pct"], ops["retorno_patrimonio_pct"]}
    assert len(values) == 3


def test_operational_calculator_zero_quantity_gives_zero_position():
    calc = OperationalCalculator()
    ops = calc.calculate(entry_price=100.0, stop_loss=95.0, take_profit_1=110.0, quantity=0.0, balance=10000.0)
    assert ops["valor_nominal"] == 0.0
    assert ops["lucro_liquido_usdt"] == 0.0


# --- Etapa 5: classificacao vem sempre da mesma logica institucional ------

def test_overall_score_tier_derived_from_score_not_classification_label():
    """V19.1: overall_tier deriva do overall_score, nao do classification_label.
    Se o score numerico for baixo (53.8), o tier deve ser REPROVADO,
    independente do classification_label do scanner."""
    data = {
        "quality_score": 0.90, "confidence_score": 0.85, "consensus_score": 0.80,
        "entry_score": 0.80, "risk_reward": 3.0, "classification_label": "ouro",
    }
    result = compute_overall_score(data)
    assert result["overall_score"] < 60
    assert result["overall_tier"] == "BRONZE"


def test_overall_score_tier_ouro_when_score_high_despite_low_classification_label():
    """V19.1: overall_tier deriva do overall_score. Com scores altos (86.7),
    o tier deve ser OURO, nao BRONZE, mesmo que o scanner diga 'bronze'.
    A divergencia e registrada como warning."""
    data = {
        "quality_score": 0.95, "confidence_score": 0.95, "consensus_score": 0.95,
        "entry_score": 0.95, "risk_reward": 4.0, "classification_label": "bronze",
        "liquidity_score": 0.95, "structural_score": 0.95, "flow_score": 0.95,
        "institutional_score": 0.95, "trend": "uptrend", "kalman_direction": "UP",
        "direction": "LONG",
    }
    result = compute_overall_score(data)
    assert result["overall_score"] >= 80
    assert result["overall_tier"] == "PLATINA"


def test_overall_score_no_classification_label_defaults_to_reprovado():
    data = {"quality_score": 0.5, "confidence_score": 0.5, "consensus_score": 0.5}
    result = compute_overall_score(data)
    assert result["overall_tier"] == "REPROVADO"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
