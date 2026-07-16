"""RFC V18.5 — Exchange Validation Gate: integracao com main.py.

Inspecao de codigo: confirma que a validacao roda no Discovery (antes de
qualquer scan) e como defesa em profundidade antes do envio ao Telegram.
"""
import inspect


class TestMainPyIntegration:
    def test_exchange_validation_instantiated(self):
        import main
        source = inspect.getsource(main)
        assert "self._exchange_validation = ExchangeValidation()" in source

    def test_discovery_filters_auto_mode_before_max_scan_pairs(self):
        import main
        source = inspect.getsource(main)
        idx = source.index("def _discover_symbols")
        block = source[idx:idx + 1600]
        assert "self._exchange_validation.filter_valid(filtered)" in block
        assert "self._exchange_validation.filter_valid(candidates)" in block

    def test_telegram_send_blocked_for_invalid_symbol(self):
        import main
        source = inspect.getsource(main)
        idx = source.index("elif not self._exchange_validation.is_valid_symbol(best_sd.symbol):")
        block = source[idx:idx + 500]
        assert "TELEGRAM BLOCKED (INVALID_SYMBOL)" in block
