import sys
import os
import time
import math

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import unittest
from ENGINE.exchange.execution_validator import (
    ExchangeExecutionValidator, ExchangeSymbolInfo,
    ExecutionValidationResult, ValidationCheckItem,
)


_REAL_SYMBOL_INFO = ExchangeSymbolInfo(
    symbol="CATONUSDT",
    tick_size=0.001,
    step_size=0.001,
    min_qty=0.001,
    max_qty=10000000.0,
    min_notional=5.0,
    max_notional=0.0,
    price_precision=3,
    qty_precision=3,
    min_leverage=1,
    max_leverage=125,
    is_active=True,
    is_futures=True,
    contract_status="TRADING",
    maintenance_margin_rate=0.005,
    taker_fee_rate=0.0006,
    maker_fee_rate=0.0002,
)

_CATONUSDT_DATA = dict(
    entry_price=936.615,
    stop_loss=920.298,
    take_profit_1=954.512,
    take_profit_2=987.411,
    quantity=46.037,
    balance=5000.0,
    leverage=12,
    direction="SHORT",
)


class TestExchangeSymbolInfoFromMEXC(unittest.TestCase):

    def test_from_mexc_full(self):
        raw = {
            "symbol": "BTCUSDT",
            "status": "TRADING",
            "pricePrecision": 2,
            "quantityPrecision": 5,
            "filters": [
                {"filterType": "PRICE_FILTER", "tickSize": "0.01", "minPrice": "0.01", "maxPrice": "1000000"},
                {"filterType": "LOT_SIZE", "stepSize": "0.00001", "minQty": "0.00001", "maxQty": "100000"},
                {"filterType": "MIN_NOTIONAL", "minNotional": "5.0"},
            ],
            "permissions": ["SPOT", "MARGIN", "FUTURES"],
        }
        info = ExchangeSymbolInfo.from_mexc_symbol(raw)
        self.assertEqual(info.symbol, "BTCUSDT")
        self.assertEqual(info.tick_size, 0.01)
        self.assertEqual(info.step_size, 0.00001)
        self.assertEqual(info.min_qty, 0.00001)
        self.assertEqual(info.max_qty, 100000.0)
        self.assertEqual(info.min_notional, 5.0)
        self.assertEqual(info.price_precision, 2)
        self.assertEqual(info.qty_precision, 5)
        self.assertTrue(info.is_active)
        self.assertTrue(info.is_futures)

    def test_from_mexc_inactive(self):
        raw = {"symbol": "X", "status": "HALT", "filters": [], "permissions": []}
        info = ExchangeSymbolInfo.from_mexc_symbol(raw)
        self.assertFalse(info.is_active)
        self.assertFalse(info.is_futures)

    def test_from_mexc_empty_filters(self):
        raw = {"symbol": "X", "status": "TRADING", "filters": [], "permissions": ["SPOT"]}
        info = ExchangeSymbolInfo.from_mexc_symbol(raw)
        self.assertEqual(info.tick_size, 0.0)
        self.assertEqual(info.step_size, 0.0)
        self.assertEqual(info.min_notional, 0.0)


class TestExchangeSymbolInfoFromBinance(unittest.TestCase):

    def test_from_binance_full(self):
        raw = {
            "symbol": "ETHUSDT",
            "status": "TRADING",
            "baseAssetPrecision": 5,
            "quotePrecision": 2,
            "filters": [
                {"filterType": "PRICE_FILTER", "tickSize": "0.01", "minPrice": "0.01", "maxPrice": "100000"},
                {"filterType": "LOT_SIZE", "stepSize": "0.001", "minQty": "0.001", "maxQty": "10000"},
                {"filterType": "MIN_NOTIONAL", "minNotional": "5.0"},
            ],
            "contractType": "PERPETUAL",
        }
        info = ExchangeSymbolInfo.from_binance_symbol(raw)
        self.assertEqual(info.symbol, "ETHUSDT")
        self.assertEqual(info.tick_size, 0.01)
        self.assertEqual(info.step_size, 0.001)
        self.assertEqual(info.min_qty, 0.001)
        self.assertEqual(info.min_notional, 5.0)
        self.assertEqual(info.price_precision, 2)
        self.assertEqual(info.qty_precision, 5)
        self.assertTrue(info.is_futures)

    def test_from_binance_not_futures(self):
        raw = {"symbol": "X", "status": "TRADING", "filters": [], "contractType": "SPOT"}
        info = ExchangeSymbolInfo.from_binance_symbol(raw)
        self.assertFalse(info.is_futures)


class TestExchangeSymbolInfoFromBybit(unittest.TestCase):

    def test_from_bybit_full(self):
        raw = {
            "symbol": "BTCUSDT",
            "status": "Trading",
            "priceFilter": {"tickSize": "0.10"},
            "lotSizeFilter": {"qtyStep": "0.001", "minOrderQty": "0.001", "maxOrderQty": "1000", "minOrderAmt": "5.0"},
            "contractType": "LinearPerpetual",
        }
        info = ExchangeSymbolInfo.from_bybit_symbol(raw)
        self.assertEqual(info.symbol, "BTCUSDT")
        self.assertEqual(info.tick_size, 0.10)
        self.assertEqual(info.step_size, 0.001)
        self.assertEqual(info.min_qty, 0.001)
        self.assertEqual(info.max_qty, 1000.0)
        self.assertEqual(info.min_notional, 5.0)
        self.assertTrue(info.is_futures)
        self.assertTrue(info.is_active)


class TestValidatorValidSignal(unittest.TestCase):

    def setUp(self):
        self.validator = ExchangeExecutionValidator(
            symbol_info=_REAL_SYMBOL_INFO,
            auto_round_prices=True,
            auto_round_quantity=True,
            block_invalid=True,
        )

    def test_valid_catonusdt_short(self):
        result = self.validator.validate(**_CATONUSDT_DATA)
        self.assertTrue(result.overall, f"Expected PASS, got: {result.hard_fail_reason}")
        self.assertEqual(result.hard_fail_reason, "")
        self.assertGreater(len(result.checks), 10)

    def test_valid_long_signal(self):
        result = self.validator.validate(
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit_1=52000.0,
            quantity=0.01,
            balance=500.0,
            leverage=10,
            direction="LONG",
        )
        self.assertTrue(result.overall, f"Expected PASS, got: {result.hard_fail_reason}")


class TestTickSizeValidation(unittest.TestCase):

    def setUp(self):
        self.validator = ExchangeExecutionValidator(
            symbol_info=ExchangeSymbolInfo(
                symbol="TEST", tick_size=0.01, step_size=0.001,
                price_precision=2, qty_precision=3,
                min_qty=0.001, max_qty=1000, min_notional=5,
                is_active=True, is_futures=True, contract_status="TRADING",
                min_leverage=1, max_leverage=125,
            ),
            block_invalid=True, tolerance=0.000001,
        )

    def test_aligned_price(self):
        result = self.validator.validate(
            entry_price=100.00, stop_loss=99.00, take_profit_1=102.00,
            quantity=1.0, balance=1000, leverage=10, direction="LONG",
        )
        self.assertTrue(result.overall)

    def test_misaligned_price(self):
        result = self.validator.validate(
            entry_price=100.005, stop_loss=99.00, take_profit_1=102.00,
            quantity=1.0, balance=1000, leverage=10, direction="LONG",
        )
        self.assertFalse(result.overall)
        tick_checks = [c for c in result.checks if "TickSize" in c.name]
        self.assertTrue(any(not c.passed for c in tick_checks))

    def test_auto_round_price_fixes_misalignment(self):
        val = ExchangeExecutionValidator(
            symbol_info=ExchangeSymbolInfo(
                symbol="TEST", tick_size=0.01, step_size=0.001,
                price_precision=2, qty_precision=3,
                min_qty=0.001, max_qty=1000, min_notional=5,
                is_active=True, is_futures=True, contract_status="TRADING",
                min_leverage=1, max_leverage=125,
            ),
            auto_round_prices=True, block_invalid=True, tolerance=0.000001,
        )
        result = val.validate(
            entry_price=100.005, stop_loss=99.00, take_profit_1=102.00,
            quantity=1.0, balance=1000, leverage=10, direction="LONG",
        )
        self.assertTrue(result.overall)
        rounded = val.round_price(100.005)
        self.assertEqual(rounded, 100.01)


class TestStepSizeValidation(unittest.TestCase):

    def setUp(self):
        self.validator = ExchangeExecutionValidator(
            symbol_info=ExchangeSymbolInfo(
                symbol="TEST", tick_size=0.01, step_size=0.1,
                price_precision=2, qty_precision=1,
                min_qty=0.1, max_qty=1000, min_notional=5,
                is_active=True, is_futures=True, contract_status="TRADING",
                min_leverage=1, max_leverage=125,
            ),
            block_invalid=True, tolerance=0.000001,
        )

    def test_aligned_quantity(self):
        result = self.validator.validate(
            entry_price=100.0, stop_loss=99.0, take_profit_1=102.0,
            quantity=1.0, balance=1000, leverage=10, direction="LONG",
        )
        self.assertTrue(result.overall)

    def test_misaligned_quantity(self):
        result = self.validator.validate(
            entry_price=100.0, stop_loss=99.0, take_profit_1=102.0,
            quantity=1.05, balance=1000, leverage=10, direction="LONG",
        )
        self.assertFalse(result.overall)

    def test_auto_round_quantity(self):
        val = ExchangeExecutionValidator(
            symbol_info=ExchangeSymbolInfo(
                symbol="TEST", tick_size=0.01, step_size=0.1,
                price_precision=2, qty_precision=1,
                min_qty=0.1, max_qty=1000, min_notional=5,
                is_active=True, is_futures=True, contract_status="TRADING",
                min_leverage=1, max_leverage=125,
            ),
            auto_round_quantity=True, block_invalid=True, tolerance=0.000001,
        )
        result = val.validate(
            entry_price=100.0, stop_loss=99.0, take_profit_1=102.0,
            quantity=1.05, balance=1000, leverage=10, direction="LONG",
        )
        self.assertTrue(result.overall)
        self.assertEqual(val.round_quantity(1.05), 1.1)


class TestLotSizeValidation(unittest.TestCase):

    def setUp(self):
        self.validator = ExchangeExecutionValidator(
            symbol_info=ExchangeSymbolInfo(
                symbol="TEST", tick_size=0.01, step_size=0.001,
                price_precision=2, qty_precision=3,
                min_qty=0.1, max_qty=100.0, min_notional=5,
                is_active=True, is_futures=True, contract_status="TRADING",
                min_leverage=1, max_leverage=125,
            ),
            block_invalid=True,
        )

    def test_below_min_lot(self):
        result = self.validator.validate(
            entry_price=100.0, stop_loss=99.0, take_profit_1=102.0,
            quantity=0.05, balance=1000, leverage=10, direction="LONG",
        )
        self.assertFalse(result.overall)
        ls_checks = [c for c in result.checks if c.name == "LotSize"]
        self.assertTrue(any(not c.passed for c in ls_checks))

    def test_above_max_lot(self):
        result = self.validator.validate(
            entry_price=100.0, stop_loss=99.0, take_profit_1=102.0,
            quantity=200.0, balance=1000, leverage=10, direction="LONG",
        )
        self.assertFalse(result.overall)

    def test_within_lot_range(self):
        result = self.validator.validate(
            entry_price=100.0, stop_loss=99.0, take_profit_1=102.0,
            quantity=1.0, balance=1000, leverage=10, direction="LONG",
        )
        self.assertTrue(result.overall)


class TestMinNotionalValidation(unittest.TestCase):

    def setUp(self):
        self.validator = ExchangeExecutionValidator(
            symbol_info=ExchangeSymbolInfo(
                symbol="TEST", tick_size=0.01, step_size=0.001,
                min_qty=0.001, max_qty=1000, min_notional=100.0,
                is_active=True, is_futures=True, contract_status="TRADING",
                min_leverage=1, max_leverage=125,
            ),
            block_invalid=True,
        )

    def test_below_min_notional(self):
        result = self.validator.validate(
            entry_price=10.0, stop_loss=9.5, take_profit_1=11.0,
            quantity=1.0, balance=1000, leverage=10, direction="LONG",
        )
        self.assertFalse(result.overall)
        mn_checks = [c for c in result.checks if c.name == "MinNotional"]
        self.assertTrue(any(not c.passed for c in mn_checks))

    def test_above_min_notional(self):
        result = self.validator.validate(
            entry_price=200.0, stop_loss=190.0, take_profit_1=220.0,
            quantity=1.0, balance=1000, leverage=10, direction="LONG",
        )
        self.assertTrue(result.overall)


class TestLeverageValidation(unittest.TestCase):

    def setUp(self):
        self.validator = ExchangeExecutionValidator(
            symbol_info=ExchangeSymbolInfo(
                symbol="TEST", tick_size=0.01, step_size=0.001,
                min_qty=0.001, max_qty=1000, min_notional=5,
                is_active=True, is_futures=True, contract_status="TRADING",
                min_leverage=5, max_leverage=20,
            ),
            block_invalid=True,
        )

    def test_below_min_leverage(self):
        result = self.validator.validate(
            entry_price=100.0, stop_loss=99.0, take_profit_1=102.0,
            quantity=1.0, balance=1000, leverage=1, direction="LONG",
        )
        self.assertFalse(result.overall)

    def test_above_max_leverage(self):
        result = self.validator.validate(
            entry_price=100.0, stop_loss=99.0, take_profit_1=102.0,
            quantity=1.0, balance=1000, leverage=50, direction="LONG",
        )
        self.assertFalse(result.overall)

    def test_within_leverage_range(self):
        result = self.validator.validate(
            entry_price=100.0, stop_loss=99.0, take_profit_1=102.0,
            quantity=1.0, balance=1000, leverage=10, direction="LONG",
        )
        self.assertTrue(result.overall)


class TestMarginValidation(unittest.TestCase):

    def setUp(self):
        self.validator = ExchangeExecutionValidator(
            symbol_info=_REAL_SYMBOL_INFO,
            block_invalid=True,
        )

    def test_margin_exceeds_balance(self):
        result = self.validator.validate(
            entry_price=1000.0, stop_loss=990.0, take_profit_1=1020.0,
            quantity=100.0, balance=500.0, leverage=10, direction="LONG",
        )
        self.assertFalse(result.overall)
        m_checks = [c for c in result.checks if c.name == "Margin"]
        self.assertTrue(any(not c.passed for c in m_checks))

    def test_margin_within_balance(self):
        result = self.validator.validate(
            entry_price=100.0, stop_loss=99.0, take_profit_1=102.0,
            quantity=1.0, balance=500.0, leverage=10, direction="LONG",
        )
        self.assertTrue(result.overall)


class TestLiquidationRisk(unittest.TestCase):

    def setUp(self):
        self.validator = ExchangeExecutionValidator(
            symbol_info=_REAL_SYMBOL_INFO,
            block_invalid=True,
        )

    def test_short_liquidation_before_stop(self):
        result = self.validator.validate(
            entry_price=100.0, stop_loss=105.0, take_profit_1=95.0,
            quantity=1.0, balance=1000, leverage=50, direction="SHORT",
        )
        liq_checks = [c for c in result.checks if c.name == "LiquidationRisk"]
        self.assertTrue(any(not c.passed for c in liq_checks))
        self.assertTrue(result.liquidation_risk)

    def test_long_liquidation_before_stop(self):
        result = self.validator.validate(
            entry_price=100.0, stop_loss=95.0, take_profit_1=105.0,
            quantity=1.0, balance=1000, leverage=50, direction="LONG",
        )
        liq_checks = [c for c in result.checks if c.name == "LiquidationRisk"]
        self.assertTrue(any(not c.passed for c in liq_checks))

    def test_liquidation_safe_short(self):
        result = self.validator.validate(
            entry_price=936.615, stop_loss=920.298, take_profit_1=954.512,
            quantity=46.037, balance=600, leverage=12, direction="SHORT",
        )
        liq = result.liquidation_price
        sl = 920.298
        self.assertGreater(liq, sl,
            f"liq={liq:.4f} must be > sl={sl:.4f} for SHORT")

    def test_liquidation_safe_long(self):
        result = self.validator.validate(
            entry_price=100.0, stop_loss=95.0, take_profit_1=105.0,
            quantity=1.0, balance=1000, leverage=10, direction="LONG",
        )
        liq = result.liquidation_price
        sl = 95.0
        self.assertLess(liq, sl,
            f"liq={liq:.4f} must be < sl={sl:.4f} for LONG")


class TestContractStatus(unittest.TestCase):

    def test_inactive_contract(self):
        info = ExchangeSymbolInfo(
            symbol="DEAD", is_active=False, contract_status="HALTED",
            min_qty=0.001, max_qty=1000, min_notional=5,
            is_futures=True, min_leverage=1, max_leverage=125,
        )
        val = ExchangeExecutionValidator(symbol_info=info, block_invalid=True)
        result = val.validate(
            entry_price=100.0, stop_loss=99.0, take_profit_1=102.0,
            quantity=1.0, balance=1000, leverage=10, direction="LONG",
        )
        self.assertFalse(result.overall)

    def test_active_contract(self):
        val = ExchangeExecutionValidator(symbol_info=_REAL_SYMBOL_INFO, block_invalid=True)
        result = val.validate(
            entry_price=100.0, stop_loss=99.0, take_profit_1=102.0,
            quantity=1.0, balance=1000, leverage=10, direction="LONG",
        )
        cs_checks = [c for c in result.checks if c.name == "ContractStatus"]
        self.assertTrue(all(c.passed for c in cs_checks))


class TestFeeCalculation(unittest.TestCase):

    def test_fees_positive(self):
        val = ExchangeExecutionValidator(symbol_info=_REAL_SYMBOL_INFO)
        result = val.validate(**_CATONUSDT_DATA)
        self.assertGreater(result.taker_fee, 0)
        self.assertGreater(result.maker_fee, 0)
        self.assertGreater(result.total_fees, 0)

    def test_net_rr_reasonable(self):
        val = ExchangeExecutionValidator(symbol_info=_REAL_SYMBOL_INFO)
        result = val.validate(**_CATONUSDT_DATA)
        self.assertGreater(result.net_rr, 0)
        self.assertGreater(result.net_profit, 0)
        self.assertGreater(result.net_loss, 0)


class TestPrecisionValidation(unittest.TestCase):

    def test_price_precision_overflow(self):
        info = ExchangeSymbolInfo(
            symbol="TEST", tick_size=0.01, step_size=0.001,
            min_qty=0.001, max_qty=1000, min_notional=5,
            price_precision=2, qty_precision=3,
            is_active=True, is_futures=True, contract_status="TRADING",
            min_leverage=1, max_leverage=125,
        )
        val = ExchangeExecutionValidator(symbol_info=info, block_invalid=True)
        result = val.validate(
            entry_price=100.123, stop_loss=99.0, take_profit_1=102.0,
            quantity=1.0, balance=1000, leverage=10, direction="LONG",
        )
        self.assertFalse(result.overall)

    def test_qty_precision_overflow(self):
        info = ExchangeSymbolInfo(
            symbol="TEST", tick_size=0.01, step_size=0.001,
            min_qty=0.001, max_qty=1000, min_notional=5,
            price_precision=2, qty_precision=1,
            is_active=True, is_futures=True, contract_status="TRADING",
            min_leverage=1, max_leverage=125,
        )
        val = ExchangeExecutionValidator(symbol_info=info, block_invalid=True)
        result = val.validate(
            entry_price=100.0, stop_loss=99.0, take_profit_1=102.0,
            quantity=1.234, balance=1000, leverage=10, direction="LONG",
        )
        self.assertFalse(result.overall)


class TestEdgeCases(unittest.TestCase):

    def test_zero_inputs(self):
        val = ExchangeExecutionValidator(symbol_info=_REAL_SYMBOL_INFO)
        result = val.validate(
            entry_price=0, stop_loss=0, take_profit_1=0,
            quantity=0, balance=0, leverage=0, direction="LONG",
        )
        self.assertFalse(result.overall)
        self.assertIn("invalid inputs", result.hard_fail_reason)

    def test_negative_inputs(self):
        val = ExchangeExecutionValidator(symbol_info=_REAL_SYMBOL_INFO)
        result = val.validate(
            entry_price=-100, stop_loss=-99, take_profit_1=-102,
            quantity=-1, balance=1000, leverage=10, direction="LONG",
        )
        self.assertFalse(result.overall)

    def test_missing_take_profit_2(self):
        val = ExchangeExecutionValidator(symbol_info=_REAL_SYMBOL_INFO)
        result = val.validate(
            entry_price=100.0, stop_loss=99.0, take_profit_1=102.0,
            take_profit_2=0,
            quantity=1.0, balance=1000, leverage=10, direction="LONG",
        )
        self.assertTrue(result.overall)

    def test_trailing_stop_check(self):
        info = ExchangeSymbolInfo(
            symbol="TEST", tick_size=0.1, step_size=0.01,
            min_qty=0.01, max_qty=1000, min_notional=5,
            is_active=True, is_futures=True, contract_status="TRADING",
            min_leverage=1, max_leverage=125,
        )
        val = ExchangeExecutionValidator(symbol_info=info, block_invalid=True)
        result = val.validate(
            entry_price=100.0, stop_loss=99.0, take_profit_1=102.0,
            quantity=1.0, balance=1000, leverage=10, direction="LONG",
            trailing_stop=101.05,
        )
        self.assertFalse(result.overall)
        tr_checks = [c for c in result.checks if "Trailing" in c.name]
        self.assertTrue(any(not c.passed for c in tr_checks))

    def test_max_notional(self):
        info = ExchangeSymbolInfo(
            symbol="TEST", tick_size=0.01, step_size=0.001,
            min_qty=0.001, max_qty=1000, min_notional=5,
            max_notional=100.0,
            is_active=True, is_futures=True, contract_status="TRADING",
            min_leverage=1, max_leverage=125,
        )
        val = ExchangeExecutionValidator(symbol_info=info, block_invalid=True)
        result = val.validate(
            entry_price=200.0, stop_loss=199.0, take_profit_1=202.0,
            quantity=1.0, balance=1000, leverage=10, direction="LONG",
        )
        self.assertFalse(result.overall)

    def test_no_block_invalid(self):
        val = ExchangeExecutionValidator(
            symbol_info=ExchangeSymbolInfo(
                symbol="TEST", tick_size=0.01, step_size=0.001,
                min_qty=0.1, max_qty=100, min_notional=5,
                is_active=True, is_futures=True, contract_status="TRADING",
                min_leverage=1, max_leverage=125,
            ),
            block_invalid=False,
        )
        result = val.validate(
            entry_price=100.0, stop_loss=99.0, take_profit_1=102.0,
            quantity=0.01, balance=1000, leverage=10, direction="LONG",
        )
        self.assertFalse(result.overall)
        self.assertEqual(result.hard_fail_reason, "")


class TestRoundPriceAndQuantity(unittest.TestCase):

    def setUp(self):
        self.validator = ExchangeExecutionValidator(
            symbol_info=ExchangeSymbolInfo(
                symbol="TEST", tick_size=0.01, step_size=0.1,
                min_qty=0.1, max_qty=1000, min_notional=5,
                is_active=True, is_futures=True, contract_status="TRADING",
                min_leverage=1, max_leverage=125,
            ),
        )

    def test_round_price_down(self):
        self.assertEqual(self.validator.round_price(100.005), 100.01)

    def test_round_price_up(self):
        self.assertEqual(self.validator.round_price(100.014), 100.01)

    def test_round_price_exact(self):
        self.assertEqual(self.validator.round_price(100.01), 100.01)

    def test_round_down_same(self):
        self.assertEqual(self.validator.round_quantity(1.04), 1.0)

    def test_round_quantity_up(self):
        self.assertEqual(self.validator.round_quantity(1.15), 1.2)

    def test_round_step_zero(self):
        val = ExchangeExecutionValidator(
            symbol_info=ExchangeSymbolInfo(
                symbol="TEST", tick_size=0.01, step_size=0,
                min_qty=0.001, max_qty=1000, min_notional=5,
                is_active=True, is_futures=True, contract_status="TRADING",
                min_leverage=1, max_leverage=125,
            ),
        )
        self.assertEqual(val.round_quantity(1.234), 1.234)


class TestLogReport(unittest.TestCase):

    def test_log_report_success(self):
        val = ExchangeExecutionValidator(symbol_info=_REAL_SYMBOL_INFO)
        result = val.validate(**_CATONUSDT_DATA)
        report = result.log_report()
        self.assertIn("PASS", report)
        self.assertIn("Execution", report)
        self.assertTrue(result.overall)

    def test_log_report_failure(self):
        val = ExchangeExecutionValidator(
            symbol_info=ExchangeSymbolInfo(
                symbol="TEST", tick_size=0.01, step_size=0.001,
                min_qty=0.1, max_qty=100, min_notional=100,
                is_active=False, is_futures=True, contract_status="HALTED",
                min_leverage=1, max_leverage=125,
            ),
            block_invalid=True,
        )
        result = val.validate(
            entry_price=100.0, stop_loss=99.0, take_profit_1=102.0,
            quantity=0.05, balance=10, leverage=50, direction="LONG",
        )
        report = result.log_report()
        self.assertIn("FAIL", report)


class TestLiquidationPriceCalculation(unittest.TestCase):

    def setUp(self):
        self.validator = ExchangeExecutionValidator(symbol_info=_REAL_SYMBOL_INFO)

    def test_short_liquidation_above_entry(self):
        liq = self.validator._ExchangeExecutionValidator__calculate_liquidation._entry if hasattr(self.validator, '_ExchangeExecutionValidator__calculate_liquidation') else None
        liq_price = self.validator._calculate_liquidation(100.0, 10, "SHORT")
        self.assertGreater(liq_price, 100.0)

    def test_long_liquidation_below_entry(self):
        liq_price = self.validator._calculate_liquidation(100.0, 10, "LONG")
        self.assertLess(liq_price, 100.0)

    def test_higher_leverage_closer_liquidation(self):
        liq_5x = self.validator._calculate_liquidation(100.0, 5, "SHORT")
        liq_20x = self.validator._calculate_liquidation(100.0, 20, "SHORT")
        self.assertLess(liq_20x, liq_5x)


class TestPerformance(unittest.TestCase):

    def test_validation_under_2ms(self):
        val = ExchangeExecutionValidator(symbol_info=_REAL_SYMBOL_INFO)
        start = time.perf_counter()
        for _ in range(100):
            val.validate(**_CATONUSDT_DATA)
        elapsed_ms = (time.perf_counter() - start) * 1000 / 100
        self.assertLess(elapsed_ms, 2.0, f"Avg {elapsed_ms:.4f}ms per validation (limit: 2ms)")


class TestResultDataclass(unittest.TestCase):

    def test_execution_result_defaults(self):
        r = ExecutionValidationResult()
        self.assertFalse(r.overall)
        self.assertEqual(r.hard_fail_reason, "")
        self.assertEqual(len(r.checks), 0)
        self.assertEqual(r.net_rr, 0.0)

    def test_execution_result_log_report_no_checks(self):
        r = ExecutionValidationResult(overall=True)
        report = r.log_report()
        self.assertIn("PASS", report)

    def test_check_item_label(self):
        c = ValidationCheckItem(name="Test", passed=True)
        self.assertEqual(c.label, "PASS")
        c = ValidationCheckItem(name="Test", passed=False)
        self.assertEqual(c.label, "FAIL")


class TestSymbolInfoEdgeCases(unittest.TestCase):

    def test_precision_from_str(self):
        from ENGINE.exchange.execution_validator import _precision_from_str
        self.assertEqual(_precision_from_str("0.01"), 2)
        self.assertEqual(_precision_from_str("0.001"), 3)
        self.assertEqual(_precision_from_str("1"), 0)
        self.assertEqual(_precision_from_str("0.0"), 0)
        self.assertEqual(_precision_from_str(""), 0)

    def test_symbol_info_defaults(self):
        info = ExchangeSymbolInfo(symbol="TEST")
        self.assertEqual(info.min_leverage, 1)
        self.assertEqual(info.max_leverage, 125)
        self.assertEqual(info.maintenance_margin_rate, 0.005)
        self.assertEqual(info.taker_fee_rate, 0.0006)
        self.assertEqual(info.maker_fee_rate, 0.0002)

    def test_symbol_info_with_no_futures(self):
        info = ExchangeSymbolInfo(symbol="X", is_futures=False)
        val = ExchangeExecutionValidator(symbol_info=info)
        result = val.validate(
            entry_price=100.0, stop_loss=99.0, take_profit_1=102.0,
            quantity=1.0, balance=1000, leverage=10, direction="LONG",
        )
        self.assertTrue(result.overall)


class TestMultiExchangeCompatibility(unittest.TestCase):

    def test_mexc_validator_construction(self):
        raw = {
            "symbol": "BTCUSDT", "status": "TRADING",
            "pricePrecision": 2, "quantityPrecision": 5,
            "filters": [
                {"filterType": "PRICE_FILTER", "tickSize": "0.01"},
                {"filterType": "LOT_SIZE", "stepSize": "0.00001", "minQty": "0.00001", "maxQty": "100000"},
                {"filterType": "MIN_NOTIONAL", "minNotional": "5.0"},
            ],
            "permissions": ["FUTURES"],
        }
        info = ExchangeSymbolInfo.from_mexc_symbol(raw)
        val = ExchangeExecutionValidator(symbol_info=info)
        result = val.validate(
            entry_price=50000.0, stop_loss=49000.0, take_profit_1=52000.0,
            quantity=0.001, balance=1000, leverage=10, direction="LONG",
        )
        self.assertTrue(result.overall)

    def test_binance_validator_construction(self):
        raw = {
            "symbol": "ETHUSDT", "status": "TRADING",
            "baseAssetPrecision": 5, "quotePrecision": 2,
            "filters": [
                {"filterType": "PRICE_FILTER", "tickSize": "0.01"},
                {"filterType": "LOT_SIZE", "stepSize": "0.001", "minQty": "0.001", "maxQty": "10000"},
                {"filterType": "MIN_NOTIONAL", "minNotional": "5.0"},
            ],
            "contractType": "PERPETUAL",
        }
        info = ExchangeSymbolInfo.from_binance_symbol(raw)
        val = ExchangeExecutionValidator(symbol_info=info)
        result = val.validate(
            entry_price=3000.0, stop_loss=2900.0, take_profit_1=3100.0,
            quantity=0.01, balance=1000, leverage=10, direction="LONG",
        )
        self.assertTrue(result.overall)

    def test_bybit_validator_construction(self):
        raw = {
            "symbol": "BTCUSDT", "status": "Trading",
            "priceFilter": {"tickSize": "0.10"},
            "lotSizeFilter": {"qtyStep": "0.001", "minOrderQty": "0.001", "maxOrderQty": "1000", "minOrderAmt": "5.0"},
            "contractType": "LinearPerpetual",
        }
        info = ExchangeSymbolInfo.from_bybit_symbol(raw)
        val = ExchangeExecutionValidator(symbol_info=info)
        result = val.validate(
            entry_price=50000.0, stop_loss=49000.0, take_profit_1=52000.0,
            quantity=0.01, balance=1000, leverage=10, direction="LONG",
        )
        self.assertTrue(result.overall)


if __name__ == "__main__":
    unittest.main()
