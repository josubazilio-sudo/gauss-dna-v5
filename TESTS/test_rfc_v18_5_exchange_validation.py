"""RFC V18.5 — Exchange Validation Gate (MEXC Futures).

Testa exclusivamente logica pura sobre respostas simuladas da API de
Futuros da MEXC (contract.mexc.com/api/v1/contract/detail) — nenhum
teste faz chamada de rede real, para manter a suite rapida e
reproduzivel. O formato de resposta simulado (data: [{symbol, apiAllowed,
...}]) reproduz exatamente o retorno real confirmado em produção.
"""
from unittest.mock import MagicMock

from ENGINE.exchange.exchange_validation import ExchangeValidation


def _mock_session(contracts):
    session = MagicMock()
    response = MagicMock()
    response.json.return_value = {"success": True, "code": 0, "data": contracts}
    response.raise_for_status.return_value = None
    session.get.return_value = response
    return session


_REAL_SAMPLE = [
    {"symbol": "BTC_USDT", "apiAllowed": True},
    {"symbol": "ETH_USDT", "apiAllowed": True},
    {"symbol": "BANANA_USDT", "apiAllowed": True},
    {"symbol": "SOL_USDT", "apiAllowed": True},
    {"symbol": "DISABLED_USDT", "apiAllowed": False},
]


def _validation_with_sample():
    return ExchangeValidation(session=_mock_session(_REAL_SAMPLE), refresh_interval=3600)


class TestIsValidSymbol:
    """Casos exatos pedidos na RFC — todos devem passar."""

    def test_btcusdt_is_valid(self):
        assert _validation_with_sample().is_valid_symbol("BTCUSDT") is True

    def test_ethusdt_is_valid(self):
        assert _validation_with_sample().is_valid_symbol("ETHUSDT") is True

    def test_bananausdt_is_valid(self):
        assert _validation_with_sample().is_valid_symbol("BANANAUSDT") is True

    def test_acnonusdt_is_invalid(self):
        assert _validation_with_sample().is_valid_symbol("ACNONUSDT") is False

    def test_attonusdt_is_invalid(self):
        assert _validation_with_sample().is_valid_symbol("ATTONUSDT") is False

    def test_invalid123_is_invalid(self):
        assert _validation_with_sample().is_valid_symbol("INVALID123") is False


class TestApiAllowedFilter:
    def test_symbol_with_api_not_allowed_is_invalid(self):
        validation = _validation_with_sample()
        assert validation.is_valid_symbol("DISABLEDUSDT") is False


class TestCaseAndFormatInsensitivity:
    def test_lowercase_symbol_matches(self):
        assert _validation_with_sample().is_valid_symbol("btcusdt") is True

    def test_underscore_format_matches(self):
        assert _validation_with_sample().is_valid_symbol("BTC_USDT") is True


class TestFilterValid:
    def test_filters_and_reports_rejected(self):
        validation = _validation_with_sample()
        symbols = ["BTCUSDT", "ETHUSDT", "ACNONUSDT", "ATTONUSDT"]
        approved = validation.filter_valid(symbols)
        assert approved == {"BTCUSDT", "ETHUSDT"}
        assert validation.last_rejected == {"ACNONUSDT", "ATTONUSDT"}

    def test_loaded_count_reflects_api_allowed_only(self):
        validation = _validation_with_sample()
        assert validation.loaded_count == 4  # 5 contratos - 1 com apiAllowed=False


class TestFailSafe:
    def test_network_failure_with_no_prior_cache_fails_open(self):
        session = MagicMock()
        session.get.side_effect = ConnectionError("timeout")
        validation = ExchangeValidation(session=session, refresh_interval=3600)
        # Sem cache anterior e API fora do ar -> aceita tudo (fail-open),
        # nunca bloqueia 100% dos sinais por uma falha de rede.
        assert validation.is_valid_symbol("QUALQUERUSDT") is True

    def test_network_failure_after_success_keeps_last_valid_list(self):
        session = _mock_session(_REAL_SAMPLE)
        validation = ExchangeValidation(session=session, refresh_interval=0.01)
        assert validation.is_valid_symbol("BTCUSDT") is True
        assert validation.is_valid_symbol("ACNONUSDT") is False

        session.get.side_effect = ConnectionError("timeout")
        import time
        time.sleep(0.02)
        # refresh interno falha silenciosamente, mas a lista anterior
        # (carregada com sucesso) continua valendo.
        assert validation.is_valid_symbol("BTCUSDT") is True
        assert validation.is_valid_symbol("ACNONUSDT") is False

    def test_malformed_response_treated_as_failure(self):
        session = MagicMock()
        response = MagicMock()
        response.json.return_value = {"success": False, "code": 1}
        response.raise_for_status.return_value = None
        session.get.return_value = response
        validation = ExchangeValidation(session=session, refresh_interval=3600)
        assert validation.is_valid_symbol("QUALQUERUSDT") is True


class TestRefreshCadence:
    def test_does_not_refetch_within_interval(self):
        session = _mock_session(_REAL_SAMPLE)
        validation = ExchangeValidation(session=session, refresh_interval=3600)
        call_count_after_init = session.get.call_count
        validation.is_valid_symbol("BTCUSDT")
        validation.is_valid_symbol("ETHUSDT")
        assert session.get.call_count == call_count_after_init

    def test_refetches_after_interval_elapsed(self):
        import time
        session = _mock_session(_REAL_SAMPLE)
        validation = ExchangeValidation(session=session, refresh_interval=0.01)
        call_count_after_init = session.get.call_count
        time.sleep(0.02)
        validation.is_valid_symbol("BTCUSDT")
        assert session.get.call_count > call_count_after_init
