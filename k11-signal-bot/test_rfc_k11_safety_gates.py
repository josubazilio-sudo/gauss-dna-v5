"""
K11 Safety Gates — regressions for production signal leakage.

Run: python -m pytest test_rfc_k11_safety_gates.py
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))


def test_signal_validator_blocks_when_current_price_is_unavailable(monkeypatch):
    import signal_validator

    monkeypatch.setattr(signal_validator, "_fetch_current_price", lambda symbol: None)

    sinal = {
        "symbol": "TEST/USDT:USDT",
        "timeframe": "30m",
        "direcao": "LONG",
        "entrada": 1.0,
        "stop": 0.9,
        "tp1": 1.2,
        "tp2": 1.35,
        "atr": 0.02,
        "candle_ts": None,
    }

    validado = signal_validator.validar(sinal)

    assert validado["valido"] is False
    assert validado["block_reason"] == "PRICE_UNAVAILABLE"


def test_runner_does_not_fallback_to_unselected_candidates_after_final_selector_rejects_all():
    runner_path = pathlib.Path(__file__).resolve().parent / "runner.py"
    src = runner_path.read_text(encoding="utf-8")

    assert "if fs_selecionados:" not in src
    assert "aprovados = fs_selecionados" in src


def test_runner_uses_k12_as_visible_bot_name_for_telegram_cards():
    runner_path = pathlib.Path(__file__).resolve().parent / "runner.py"
    src = runner_path.read_text(encoding="utf-8")

    assert 'bot_name="K11"' not in src
    assert 'bot_name="K12"' in src
