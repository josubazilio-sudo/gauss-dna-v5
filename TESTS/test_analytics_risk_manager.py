"""RFC V20.0 Fase 4 — Gestao de Risco (calculadora, nunca altera sinal)."""
from ENGINE.analytics import risk_manager as rm


def test_calculate_position_basic_math():
    result = rm.calculate_position(banca=1000.0, risco_pct=0.02, entrada=100.0, stop=98.0)
    # valor arriscado = 1000 * 0.02 = 20; price_risk = 2 -> quantidade = 10
    assert result["quantidade"] == 10.0
    assert result["perda_maxima"] == 20.0


def test_calculate_position_with_take_profit_computes_rr_and_lucro():
    result = rm.calculate_position(banca=1000.0, risco_pct=0.02, entrada=100.0, stop=98.0, take_profit=104.0)
    assert result["rr"] == 2.0  # 4 de lucro / 2 de risco
    assert result["lucro_esperado"] > 0


def test_calculate_position_without_take_profit_rr_is_zero():
    result = rm.calculate_position(banca=1000.0, risco_pct=0.02, entrada=100.0, stop=98.0)
    assert result["rr"] == 0.0


def test_calculate_position_zero_banca_returns_safe_empty():
    result = rm.calculate_position(banca=0.0, risco_pct=0.02, entrada=100.0, stop=98.0)
    assert result["quantidade"] == 0.0


def test_calculate_position_entry_equals_stop_returns_safe_empty():
    result = rm.calculate_position(banca=1000.0, risco_pct=0.02, entrada=100.0, stop=100.0)
    assert result["quantidade"] == 0.0


def test_calculate_position_negative_risco_pct_returns_safe_empty():
    result = rm.calculate_position(banca=1000.0, risco_pct=-0.01, entrada=100.0, stop=98.0)
    assert result["quantidade"] == 0.0


def test_suggest_leverage_lower_for_higher_risk():
    low_risk_leverage = rm.suggest_leverage(0.01)
    high_risk_leverage = rm.suggest_leverage(0.10)
    assert low_risk_leverage > high_risk_leverage


def test_calculate_position_never_imports_decision_engine():
    """Garante isolamento estrutural: a calculadora de risco nao pode
    influenciar nem depender do Decision Engine/sinais reais."""
    import inspect
    source = inspect.getsource(rm)
    assert "ENGINE.decision" not in source
    assert "ENGINE.scanner" not in source
