"""RFC V25.3 — Auditoria da origem dos sinais do Telegram.

Cobre o fingerprint temporario de instancia (servidor, PID, build) anexado
a cada sinal, usado para rastrear a origem exata de qualquer mensagem
publicada no Telegram.
"""
import sys
import inspect
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from SERVICES.telegram.telegram_formatter import TelegramFormatter


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
        "penalty_details": [],
        "quantity": 10.0, "balance": 1000.0, "leverage": 5.0,
    }


class TestFingerprintNoTelegram:
    def test_fingerprint_fields_rendered_when_present(self):
        data = _full_signal_dict()
        data["fingerprint"] = {"server": "VPS-GAUSS", "pid": 1563310, "build": "d687290-20260714-2238"}
        msg = TelegramFormatter.format_signal(data)
        assert "Servidor: VPS-GAUSS" in msg
        assert "PID: 1563310" in msg
        assert "Build: d687290-20260714-2238" in msg

    def test_no_fingerprint_lines_when_absent(self):
        """Compatibilidade retroativa: sinal sem fingerprint nao quebra e nao mostra linhas vazias."""
        msg = TelegramFormatter.format_signal(_full_signal_dict())
        assert "Servidor:" not in msg
        assert "PID:" not in msg
        assert "Build:" not in msg


class TestFingerprintComputedOnce:
    def test_main_py_computes_fingerprint_at_startup(self):
        import main
        source = inspect.getsource(main.QuantOSApp.start)
        assert "self._fingerprint" in source
        assert "gethostname" in source

    def test_main_py_attaches_fingerprint_to_every_signal(self):
        import main
        source = inspect.getsource(main)
        assert 'data["fingerprint"] = self._fingerprint' in source
