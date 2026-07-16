"""RFC V20.2 — Correcao de Consistencia do Sinal.

Cobre: formula corrigida de retorno_margem_pct, validacao final de
apresentacao, unificacao de classificacao e remocao de penalizacao
duplicada no card do Telegram. Nao toca em Scanner/Decision Engine/
gates/thresholds/calculos de entrada.
"""
import pytest

from ENGINE.common.operational import OperationalCalculator, _derive_tier
from SERVICES.telegram.telegram_validator import validate_presentation_consistency
from SERVICES.telegram.telegram_formatter import TelegramFormatter


# --- Formula de retorno sobre margem -----------------------------------------

def test_retorno_margem_pct_uses_margin_not_max_loss():
    calc = OperationalCalculator()
    ops = calc.calculate(
        entry_price=100.0, stop_loss=98.0, take_profit_1=104.0,
        quantity=10.0, balance=1000.0, leverage=5.0,
    )
    # posicao=1000, margem=1000/5=200; lucro=10*4=40
    # retorno sobre margem = 40/200*100 = 20.0 (nao 40/perda_maxima(20)*100=200!)
    assert ops["margem_utilizada_usdt"] == 200.0
    assert ops["lucro_liquido_usdt"] == 40.0
    assert ops["retorno_margem_pct"] == pytest.approx(20.0)


def test_retorno_margem_pct_no_longer_equals_old_broken_formula():
    calc = OperationalCalculator()
    ops = calc.calculate(
        entry_price=100.0, stop_loss=98.0, take_profit_1=104.0,
        quantity=10.0, balance=1000.0, leverage=5.0,
    )
    old_broken_value = ops["lucro_liquido_usdt"] / ops["perda_maxima_usdt"] * 100.0
    assert ops["retorno_margem_pct"] != pytest.approx(old_broken_value)


def test_retorno_margem_pct_zero_when_no_leverage_info():
    calc = OperationalCalculator()
    ops = calc.calculate(
        entry_price=100.0, stop_loss=98.0, take_profit_1=104.0,
        quantity=0.0, balance=1000.0,
    )
    assert ops["retorno_margem_pct"] == 0.0


# --- validate_presentation_consistency ---------------------------------------

def _valid_long_signal():
    return {
        "direction": "LONG", "entry_price": 100.0, "stop_loss": 98.0,
        "take_profit_1": 104.0, "risk_reward": 2.0,
        "overall_score": {"overall_score": 78.0, "overall_tier": "OURO"},
    }


def test_validate_presentation_consistency_accepts_coherent_long_signal():
    ok, reason = validate_presentation_consistency(_valid_long_signal())
    assert ok is True


def test_validate_presentation_consistency_rejects_zero_entry_price():
    data = _valid_long_signal()
    data["entry_price"] = 0
    ok, reason = validate_presentation_consistency(data)
    assert ok is False


def test_validate_presentation_consistency_rejects_long_with_stop_above_entry():
    data = _valid_long_signal()
    data["stop_loss"] = 102.0  # stop acima da entrada para um LONG -> invalido
    ok, reason = validate_presentation_consistency(data)
    assert ok is False
    assert "fora de ordem" in reason


def test_validate_presentation_consistency_rejects_short_with_wrong_price_order():
    data = {
        "direction": "SHORT", "entry_price": 100.0, "stop_loss": 98.0,  # deveria ser > entry
        "take_profit_1": 96.0, "risk_reward": 2.0,
    }
    ok, reason = validate_presentation_consistency(data)
    assert ok is False


def test_validate_presentation_consistency_accepts_coherent_short_signal():
    data = {
        "direction": "SHORT", "entry_price": 100.0, "stop_loss": 102.0,
        "take_profit_1": 96.0, "risk_reward": 2.0,
    }
    ok, reason = validate_presentation_consistency(data)
    assert ok is True


def test_validate_presentation_consistency_rejects_rr_mismatch_with_prices():
    data = _valid_long_signal()
    data["risk_reward"] = 10.0  # precos indicam RR=2.0, nao 10.0
    ok, reason = validate_presentation_consistency(data)
    assert ok is False
    assert "RR exibido" in reason


def test_validate_presentation_consistency_rejects_tier_mismatch_with_score():
    data = _valid_long_signal()
    data["overall_score"] = {"overall_score": 45.0, "overall_tier": "OURO"}  # 45 -> REPROVADO, nao OURO
    ok, reason = validate_presentation_consistency(data)
    assert ok is False
    assert "Tier exibido" in reason


def test_validate_presentation_consistency_reuses_derive_tier_not_duplicated():
    """Garante que a validacao reaproveita _derive_tier() ja existente
    (fonte unica de verdade), nao reimplementa a logica de faixas."""
    import inspect
    from SERVICES.telegram import telegram_validator
    source = inspect.getsource(telegram_validator)
    assert "_derive_tier" in source
    assert "CLASSIFICATION_RANGES" not in source  # nao duplica a tabela


def test_validate_presentation_consistency_ok_without_overall_score():
    data = _valid_long_signal()
    del data["overall_score"]
    ok, reason = validate_presentation_consistency(data)
    assert ok is True


# --- Formatter: classificacao unica, sem penalizacao duplicada --------------

def _full_signal_dict():
    return {
        "symbol": "CHZUSDT", "timeframe": "1h", "direction": "SHORT",
        "entry_price": 0.017, "stop_loss": 0.0172, "take_profit_1": 0.0166,
        "risk_reward": 2.0, "quality_score": 0.73, "confidence_score": 0.80,
        "consensus_score": 0.75, "classification_label": "prata",
        "overall_score": {
            "overall_score": 78.0, "overall_bar": "", "overall_tier": "OURO",
            "overall_tier_emoji": "",
        },
        "overall_score_value": 78.0,
        "penalty_reasons": [],
        "penalty_details": [{"gate": "Kalman", "peso_perdido": 5, "motivo": "teste"}],
        "quantity": 10.0, "balance": 1000.0, "leverage": 5.0,
    }


def test_formatted_card_shows_aprovado_header():
    """RFC V19.1: score 60-79 mostra APROVADO no header."""
    msg = TelegramFormatter.format_signal(_full_signal_dict())
    assert "APROVADO" in msg
    assert msg.count("Score") == 1


def test_formatted_card_shows_no_penalty_details():
    """RFC V19.1: penalty_details nao aparece mais no card."""
    data = _full_signal_dict()
    data["penalty_reasons"] = ["Fake penalty (peso: 0.10)"]
    msg = TelegramFormatter.format_signal(data)
    assert "Kalman" not in msg  # penalty_details removido do card
