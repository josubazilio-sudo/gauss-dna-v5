import unittest
from unittest.mock import MagicMock


class TestTelegramFormatter(unittest.TestCase):
    def setUp(self):
        from SERVICES.telegram.telegram_formatter import TelegramFormatter
        self.formatter = TelegramFormatter

    def _make_signal(self, **overrides):
        signal = MagicMock()
        defaults = {
            'trace_id': 'TEST-001',
            'symbol': 'BTCUSDT',
            'timeframe': '1h',
            'direction': 'long',
            'entry_price': 50000.0,
            'stop_loss': 49500.0,
            'take_profit_1': 51000.0,
            'take_profit_2': 52000.0,
            'risk_reward': 2.0,
            'quality_score': 0.75,
            'confidence_score': 0.82,
            'institutional_score': 0.65,
            'trend': 'uptrend',
            'kalman_direction': 'UP',
            'kalman_confidence': 0.85,
            'kalman_trend_state': 'continuing',
            'kalman_tendency': 0.5,
            'classification_label': 'ouro',
            'reject_reason': '',
            'approval_reasons': ['Tendencia alinhada', 'BOS confirmado'],
            'penalty_reasons': [],
            'adx': 0.0,
            'rvol': 0.0,
            'atr_value': 0.0,
            'flow_score': 0.0,
            'overall_score_value': 82.5,
            'overall_score_bar': '\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2591\u2591',
            'overall_score_tier': 'GOLD',
            'conviction_level': 'Alta',
            'expectancy_level': 'Moderada',
            'time_to_tp1': '4 \u2013 12 horas',
            'structural_score': 0.70,
            'liquidity_score': 0.65,
            'consensus_score': 0.78,
            'engine_version': 'V18.2',
            'cycle_id': 42,
            'audit': {
                'signal_id': 'TEST-001',
                'cycle_id': 42,
                'engine_version': 'V18.2',
                'processing_time_ms': 1250.5,
                'timestamp_utc': '2026-07-11T12:00:00',
            },
        }
        for k, v in {**defaults, **overrides}.items():
            setattr(signal, k, v)
        return signal

    def test_validity(self):
        signal = self._make_signal(direction='short')
        formatted = self.formatter.format_signal(signal)
        self.assertIn("SHORT", formatted)
        self.assertIn("NOVO SINAL", formatted)

    def _verify_field(self, formatted: str, field: str, value: str) -> bool:
        formatted_lower = formatted.lower()
        return value.lower() in formatted_lower

    def test_consensus(self):
        signal = self._make_signal(quality_score=0.75, confidence_score=0.82)
        formatted = self.formatter.format_signal(signal)
        self.assertTrue(self._verify_field(formatted, "quality", "75.0"))
        self.assertTrue(self._verify_field(formatted, "confiança", "82.0"))

    def test_prices(self):
        signal = self._make_signal(entry_price=100.0, stop_loss=75.0, take_profit_1=200.0, risk_reward=2.5)
        formatted = self.formatter.format_signal(signal)
        self.assertIn("100.00", formatted)
        self.assertIn("75.00", formatted)
        self.assertIn("2.50", formatted)

    def test_trend(self):
        signal = self._make_signal(trend='uptrend')
        formatted = self.formatter.format_signal(signal)
        self.assertIn("alta", formatted.lower())

    def test_trend_ranging(self):
        signal = self._make_signal(trend='ranging')
        formatted = self.formatter.format_signal(signal)
        self.assertIn("lateral", formatted.lower())

    def test_kalman(self):
        signal = self._make_signal(kalman_direction='UP', kalman_confidence=0.85)
        formatted = self.formatter.format_signal(signal)
        self.assertIn("UP", formatted)
        self.assertIn("Kalman", formatted)

    def test_classification(self):
        signal = self._make_signal(classification_label='ouro')
        formatted = self.formatter.format_signal(signal)
        self.assertIn("ouro", formatted.lower())

    def test_no_none_fields(self):
        signal = self._make_signal(trend='', kalman_direction='UNKNOWN', classification_label='reprovado')
        formatted = self.formatter.format_signal(signal)
        self.assertNotIn("None", formatted)

    def test_low_price_asset_does_not_render_zero(self):
        signal = self._make_signal(
            entry_price=0.00001234,
            stop_loss=0.00001100,
            take_profit_1=0.00001500,
            take_profit_2=0.00001800,
            risk_reward=2.0,
        )
        formatted = self.formatter.format_signal(signal)
        self.assertIn("0.00001234", formatted)

    def test_dict_input(self):
        data = {
            'symbol': 'ETHUSDT',
            'timeframe': '4h',
            'direction': 'long',
            'entry_price': 3000.0,
            'stop_loss': 2900.0,
            'take_profit_1': 3200.0,
            'take_profit_2': 3400.0,
            'risk_reward': 2.0,
            'quality': 0.65,
            'confidence': 0.70,
            'institutional_score': 0.55,
            'trend': 'uptrend',
            'kalman_direction': 'UP',
            'kalman_confidence': 0.75,
            'classification_label': 'prata',
            'trace_id': 'DICT-001',
            'reject_reason': '',
            'overall_score_value': 75.0,
            'overall_score_bar': '\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2591\u2591\u2591',
            'overall_score_tier': 'SILVER',
            'conviction_level': 'Moderada',
            'expectancy_level': 'Baixa',
            'time_to_tp1': '1 \u2013 4 horas',
            'structural_score': 0.60,
            'liquidity_score': 0.55,
            'consensus_score': 0.72,
            'engine_version': 'V18.2',
            'cycle_id': 10,
            'audit': {
                'signal_id': 'DICT-001',
                'cycle_id': 10,
                'engine_version': 'V18.2',
                'processing_time_ms': 800.0,
            },
        }
        formatted = self.formatter.format_signal(data)
        self.assertIn("ETHUSDT", formatted)
        self.assertIn("LONG", formatted)
        self.assertIn("3000.00", formatted)
        self.assertIn("prata", formatted.lower())

    # --- V18.2 NEW TESTS ---

    def test_overall_score_displayed(self):
        signal = self._make_signal()
        formatted = self.formatter.format_signal(signal)
        self.assertIn("\u00cdndice Geral", formatted)
        self.assertIn("GOLD", formatted)
        self.assertIn("82.5", formatted)

    def test_setup_strength_displayed(self):
        signal = self._make_signal()
        formatted = self.formatter.format_signal(signal)
        self.assertIn("For\u00e7a do Setup", formatted)
        self.assertIn("Alta", formatted)
        self.assertIn("Moderada", formatted)
        self.assertIn("4 \u2013 12 horas", formatted)

    def test_audit_footer_displayed(self):
        signal = self._make_signal()
        formatted = self.formatter.format_signal(signal)
        self.assertIn("Auditoria", formatted)
        self.assertIn("TEST-001", formatted)
        self.assertIn("V18.2", formatted)
        self.assertIn("Ciclo: #42", formatted)
        self.assertIn("1250.5ms", formatted)

    def test_operational_retorno_displayed(self):
        signal = self._make_signal(
            quality_score=0.85,
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit_1=52000.0,
            risk_reward=2.0,
        )
        formatted = self.formatter.format_signal(signal)
        self.assertIn("Retorno", formatted)
        self.assertIn("Alavancagem", formatted)
        self.assertIn("Lucro", formatted)
        self.assertIn("Perda", formatted)

    def test_institutional_consensus_displayed(self):
        signal = self._make_signal(consensus_score=0.78)
        formatted = self.formatter.format_signal(signal)
        self.assertIn("Consenso", formatted)
        self.assertIn("78.0", formatted)

    def test_structure_and_liquidity_displayed(self):
        signal = self._make_signal(structural_score=0.70, liquidity_score=0.65)
        formatted = self.formatter.format_signal(signal)
        self.assertIn("Estrutura", formatted)
        self.assertIn("Liquidez", formatted)

    def test_flow_metric_displayed(self):
        signal = self._make_signal(flow_score=0.60)
        formatted = self.formatter.format_signal(signal)
        self.assertIn("Fluxo", formatted)

    def test_rejected_signal_has_no_classification(self):
        signal = self._make_signal(classification_label='reprovado')
        formatted = self.formatter.format_signal(signal)
        # Without classification, check overall and audit still show
        self.assertIn("Auditoria", formatted)
        self.assertIn("GOLD", formatted)

    def test_dict_with_overall_as_dict(self):
        data = {
            'symbol': 'SOLUSDT',
            'timeframe': '1h',
            'direction': 'SHORT',
            'entry_price': 150.0,
            'stop_loss': 155.0,
            'take_profit_1': 140.0,
            'risk_reward': 2.0,
            'quality': 0.80,
            'confidence': 0.85,
            'trace_id': 'DICT-002',
            'overall_score': {
                'overall_score': 88.0,
                'overall_bar': '\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2588\u2591',
                'overall_tier': 'GOLD',
                'overall_tier_emoji': '\U0001f3c6',
            },
            'conviction_level': 'Alta',
            'expectancy_level': 'Moderada',
            'time_to_tp1': '1 \u2013 4 horas',
            'engine_version': 'V18.2',
            'cycle_id': 99,
            'audit': {'signal_id': 'DICT-002', 'engine_version': 'V18.2'},
        }
        formatted = self.formatter.format_signal(data)
        self.assertIn("88.0", formatted)
        self.assertIn("GOLD", formatted)
        self.assertIn("SHORT", formatted)

    def test_no_overall_score_fallback(self):
        data = {
            'symbol': 'ADAUSDT',
            'timeframe': '4h',
            'direction': 'long',
            'entry_price': 1.0,
            'stop_loss': 0.95,
            'take_profit_1': 1.10,
            'risk_reward': 2.0,
            'quality': 0.70,
            'confidence': 0.75,
            'trace_id': 'FALLBACK',
        }
        formatted = self.formatter.format_signal(data)
        self.assertIn("ADAUSDT", formatted)
        self.assertIn("LONG", formatted)


if __name__ == '__main__':
    unittest.main()
