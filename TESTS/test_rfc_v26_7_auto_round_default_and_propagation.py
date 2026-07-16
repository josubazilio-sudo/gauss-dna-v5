"""RFC V26.7 — AUTO_ROUND_PRICES/AUTO_ROUND_QTY: default True + propagacao.

Causa raiz do Execution Validator bloqueando ~100% dos sinais: nada no
pipeline arredondava entry/stop/tp/quantidade para o tick_size/step_size
do simbolo antes da checagem de alinhamento, e o default de
AUTO_ROUND_PRICES/AUTO_ROUND_QTY era "false" — ou seja, precos calculados
via ponto flutuante (que praticamente nunca caem exatos num multiplo do
tick_size) sempre reprovavam TickSize_*/PricePrecision_*/StepSize/
QtyPrecision juntos, bloqueando o sinal, mesmo sendo um sinal valido.

O mecanismo de auto-round ja existia e ja era testado
(TESTS/test_rfc_v22_execution_validator.py) — so nunca estava ligado por
default, e mesmo ligado, a validacao nao devolvia os valores arredondados
para quem chama (main.py continuava usando os precos brutos no resto do
pipeline). Este arquivo cobre as duas pecas que faltavam.
"""
import inspect

from ENGINE.scanner.scanner_config import AUTO_ROUND_PRICES, AUTO_ROUND_QUANTITY
from ENGINE.exchange.execution_validator import ExchangeExecutionValidator, ExchangeSymbolInfo


def _default_symbol_info(symbol="TESTUSDT"):
    return ExchangeSymbolInfo(
        symbol=symbol, tick_size=0.001, step_size=0.001,
        min_qty=0.001, max_qty=1000000.0, min_notional=5.0,
        price_precision=3, qty_precision=3,
    )


def test_auto_round_prices_defaults_to_true():
    assert AUTO_ROUND_PRICES is True


def test_auto_round_quantity_defaults_to_true():
    assert AUTO_ROUND_QUANTITY is True


def test_realistic_computed_price_fails_without_auto_round():
    """Reproduz o bloqueio real: um preco tipico calculado por matematica
    de ponto flutuante (nao alinhado a tick_size=0.001) reprova sem
    auto-round — confirmando a causa raiz do EXECUTION VALIDATOR BLOCKED
    visto em producao."""
    validator = ExchangeExecutionValidator(
        symbol_info=_default_symbol_info(),
        auto_round_prices=False, auto_round_quantity=False,
        block_invalid=True, tolerance=0.000001,
    )
    result = validator.validate(
        entry_price=1.56350417, stop_loss=1.56100892,
        take_profit_1=1.56850123, quantity=127.34981,
        balance=10000.0, leverage=5.0, direction="LONG",
    )
    assert result.overall is False
    assert "TickSize_Entry" in result.hard_fail_reason
    assert "StepSize" in result.hard_fail_reason


def test_same_realistic_price_passes_with_auto_round():
    """O mesmo preco/quantidade do teste anterior passa quando o
    auto-round (agora default) esta ativo — sem alterar Decision Engine,
    Consensus, thresholds ou qualquer gate."""
    validator = ExchangeExecutionValidator(
        symbol_info=_default_symbol_info(),
        auto_round_prices=AUTO_ROUND_PRICES, auto_round_quantity=AUTO_ROUND_QUANTITY,
        block_invalid=True, tolerance=0.000001,
    )
    result = validator.validate(
        entry_price=1.56350417, stop_loss=1.56100892,
        take_profit_1=1.56850123, quantity=127.34981,
        balance=10000.0, leverage=5.0, direction="LONG",
    )
    assert result.overall is True


def test_round_price_and_round_quantity_produce_tick_aligned_values():
    validator = ExchangeExecutionValidator(symbol_info=_default_symbol_info())
    rounded_price = validator.round_price(1.56350417)
    rounded_qty = validator.round_quantity(127.34981)
    assert round(rounded_price % 0.001, 6) in (0.0, 0.001)
    assert round(rounded_qty % 0.001, 6) in (0.0, 0.001)


def test_main_py_propagates_rounded_values_back_to_data():
    """RFC V26.7: quando AUTO_ROUND_PRICES/AUTO_ROUND_QUANTITY estao
    ativos, main.py deve atualizar data['entry_price']/['stop_loss']/
    ['take_profit_1']/['take_profit_2']/['quantity'] com os valores
    arredondados — senao Telegram e auditoria continuam mostrando os
    precos brutos, nao alinhados ao exchange, mesmo com a checagem
    passando."""
    import main
    source = inspect.getsource(main)
    idx = source.index("elif AUTO_ROUND_PRICES or AUTO_ROUND_QUANTITY:")
    block = source[idx:idx + 1400]
    assert 'data["entry_price"] = _exec_val.round_price(' in block
    assert 'data["stop_loss"] = _exec_val.round_price(' in block
    assert 'data["take_profit_1"] = _exec_val.round_price(' in block
    assert 'data["quantity"] = _exec_val.round_quantity(' in block
