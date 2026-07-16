"""RFC V18.6 — Trend Hard Gate + Position Size Fix

Testes:
1. Trend Hard Gate (MA50/MA200) no decision_engine.py
2. Position sizing usa QUANTOS_ACCOUNT_SIZE diretamente
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from ENGINE.scanner.scanner_config import ACCOUNT_SIZE, LEVERAGE_MAX_USER


class TestPositionSizeUsesAccountSize:
    """RFC V18.6 Item 2: position sizing usa QUANTOS_ACCOUNT_SIZE."""

    def test_calculate_position_size_uses_account_size_directly(self):
        from BOTS.mexc.trading.risk_manager import BotRiskManager
        from BOTS.mexc.trading.position_manager import BotPositionManager
        from BOTS.mexc.bot_config import BotConfig

        cfg = BotConfig()
        pm = BotPositionManager(cfg, None)
        rm = BotRiskManager(cfg, pm)

        entry_price = 100.0
        qty = rm.calculate_position_size(
            balance=9999.0,  # balance parameter is ignored
            entry_price=entry_price,
            stop_loss=95.0,
            quality_score=0.9,
        )
        expected_qty = ACCOUNT_SIZE * cfg.leverage / entry_price
        assert qty == expected_qty, (
            f"Esperava {expected_qty}, obteve {qty}. "
            f"ACCOUNT_SIZE={ACCOUNT_SIZE}, leverage={cfg.leverage}"
        )
        assert qty > 0

    def test_position_size_matches_rfc_example(self):
        from BOTS.mexc.trading.risk_manager import BotRiskManager
        from BOTS.mexc.trading.position_manager import BotPositionManager
        from BOTS.mexc.bot_config import BotConfig

        cfg = BotConfig()
        pm = BotPositionManager(cfg, None)
        rm = BotRiskManager(cfg, pm)

        entry_price = 1.0
        qty = rm.calculate_position_size(
            balance=ACCOUNT_SIZE,
            entry_price=entry_price,
            stop_loss=0.97,
        )
        expected_nominal = ACCOUNT_SIZE * cfg.leverage
        nominal_value = qty * entry_price
        margin_used = nominal_value / cfg.leverage

        assert nominal_value == expected_nominal, (
            f"Valor nominal {nominal_value} != esperado {expected_nominal}"
        )
        assert margin_used == ACCOUNT_SIZE, (
            f"Margem {margin_used} != ACCOUNT_SIZE {ACCOUNT_SIZE}"
        )

    def test_position_size_zero_for_invalid_entry(self):
        from BOTS.mexc.trading.risk_manager import BotRiskManager
        from BOTS.mexc.trading.position_manager import BotPositionManager
        from BOTS.mexc.bot_config import BotConfig

        cfg = BotConfig()
        pm = BotPositionManager(cfg, None)
        rm = BotRiskManager(cfg, pm)

        qty = rm.calculate_position_size(
            balance=ACCOUNT_SIZE,
            entry_price=0.0,
            stop_loss=0.0,
        )
        assert qty == 0.0

    def test_main_py_passes_correct_quantity_to_telegram(self):
        import main as main_module
        source_lines = []
        with open(main_module.__file__, "r", encoding="utf-8") as f:
            source_lines = f.readlines()

        data_assignment_found = False
        for i, line in enumerate(source_lines):
            if 'data["quantity"]' in line and "real_quantity" in line:
                data_assignment_found = True
                break

        assert data_assignment_found, (
            "main.py deve definir data['quantity'] a partir de "
            "calculate_position_size para o Telegram exibir o valor correto"
        )

    def test_bot_engine_passes_score_to_calculate_position_size(self):
        from BOTS.mexc import bot_engine
        source = []
        with open(bot_engine.__file__, "r", encoding="utf-8") as f:
            source = f.readlines()

        found = False
        for line in source:
            if "calculate_position_size" in line and "quality_score" in line:
                found = True
                break

        assert found, (
            "bot_engine.py deve chamar calculate_position_size com quality_score"
        )

    def test_account_size_not_zero(self):
        assert ACCOUNT_SIZE > 0, "QUANTOS_ACCOUNT_SIZE deve ser > 0"
        assert ACCOUNT_SIZE == 200.0, (
            f"QUANTOS_ACCOUNT_SIZE deve ser 200, obteve {ACCOUNT_SIZE}"
        )

    def test_leverage_not_zero(self):
        assert LEVERAGE_MAX_USER > 0, "LEVERAGE_MAX_USER deve ser > 0"
        assert LEVERAGE_MAX_USER == 25.0, (
            f"LEVERAGE_MAX_USER deve ser 25, obteve {LEVERAGE_MAX_USER}"
        )

    def test_operational_calculator_shows_correct_values(self):
        from ENGINE.common.operational import OperationalCalculator

        calc = OperationalCalculator()
        entry = 100.0
        stop = 95.0
        tp1 = 110.0
        quantity = ACCOUNT_SIZE * 25 / entry
        balance = ACCOUNT_SIZE
        leverage = 25.0

        ops = calc.calculate(entry, stop, tp1, quantity, balance, leverage)

        assert ops["valor_nominal"] == ACCOUNT_SIZE * leverage, (
            f"Valor nominal {ops['valor_nominal']} != {ACCOUNT_SIZE * leverage}"
        )
        assert ops["margem_utilizada_usdt"] == ACCOUNT_SIZE, (
            f"Margem {ops['margem_utilizada_usdt']} != {ACCOUNT_SIZE}"
        )
        assert ops["quantidade"] == quantity, (
            f"Quantidade {ops['quantidade']} != {quantity}"
        )
        assert ops["alavancagem_efetiva"] == leverage


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
