import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ENGINE.watchdog.watchdog_integration import WatchdogIntegration
from ENGINE.scanner.scanner_config import MAX_SCAN_PAIRS


class FakeApp:
    def __init__(self):
        self._symbols = ["BTCUSDT"]
        self._last_heartbeat = 0.0


class FakeTelegram:
    """Simula o TelegramService real: so tem send_diagnostic, nao send_alert."""

    def __init__(self):
        self.sent = []

    def send_diagnostic(self, message: str):
        self.sent.append(message)


class TestScanStallThreshold(unittest.TestCase):
    """Regressao: threshold fixo de 120s disparava falso-positivo de
    'scanner travado' repetidamente durante ciclos reais e longos (500
    pares reais na MEXC levam ~20-30min). O threshold agora escala com
    QUANTOS_MAX_SCAN_PAIRS."""

    def test_threshold_has_floor_of_120s(self):
        wd = WatchdogIntegration(app=FakeApp())
        self.assertGreaterEqual(wd._scan_stall_threshold, 120)

    def test_threshold_scales_with_configured_scan_size(self):
        wd = WatchdogIntegration(app=FakeApp())
        if MAX_SCAN_PAIRS is not None:
            self.assertGreaterEqual(wd._scan_stall_threshold, MAX_SCAN_PAIRS * 5)
        else:
            self.assertEqual(wd._scan_stall_threshold, 3600)


class TestTelegramAlert(unittest.TestCase):
    """Regressao: _telegram_alert chamava tg.send_alert(), metodo
    inexistente em TelegramService (so existe send_diagnostic). O erro
    era engolido silenciosamente, entao nenhum alerta de watchdog jamais
    chegava ao Telegram."""

    def test_alert_uses_existing_telegram_method(self):
        app = FakeApp()
        app._telegram = FakeTelegram()
        wd = WatchdogIntegration(app=app)

        wd._telegram_alert("teste de alerta")

        self.assertEqual(len(app._telegram.sent), 1)
        self.assertIn("teste de alerta", app._telegram.sent[0])

    def test_alert_does_not_raise_when_telegram_missing(self):
        app = FakeApp()
        wd = WatchdogIntegration(app=app)
        wd._telegram_alert("sem telegram configurado")  # nao deve lancar


if __name__ == "__main__":
    unittest.main()
