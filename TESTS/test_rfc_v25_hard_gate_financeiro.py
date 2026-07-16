"""RFC V25 — Hard Gate Financeiro e Unificacao do Dimensionamento de Capital.

Cobre os 3 bugs de causa raiz corrigidos:
1. Saldo em paper trading vinha hardcoded em 10000.0, ignorando QUANTOS_ACCOUNT_SIZE.
2. Alavancagem sempre caia para 1.0 (BotConfig nunca teve o atributo `leverage`).
3. Math Auditor (V21) nao validava contra os limites reais da conta (capital,
   alavancagem maxima) e o conflito MTF isolado nao bloqueava o sinal.
"""
import sys
import inspect
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from ENGINE.scanner.scanner_config import ACCOUNT_SIZE, LEVERAGE_MAX_USER
from ENGINE.auditor.institutional_math_auditor import InstitutionalMathAuditor


class TestBotConfigLeverage:
    """RFC V25 Item 2: alavancagem real, nao mais fixa em 1.0."""

    def test_default_leverage_matches_quantos_leverage_max(self):
        from BOTS.mexc.bot_config import BotConfig
        cfg = BotConfig()
        assert cfg.leverage == LEVERAGE_MAX_USER

    def test_main_py_no_longer_has_dead_hasattr_fallback(self):
        import main
        source = inspect.getsource(main)
        assert "self._config.leverage if hasattr(self._config, 'leverage') else 1.0" not in source
        assert 'data["leverage"] = self._config.leverage' in source


class TestBalanceSingleSourceOfTruth:
    """RFC V25 Item 1: paper trading usa QUANTOS_ACCOUNT_SIZE, nao 10000 fixo."""

    def test_update_balance_uses_account_size_not_hardcoded_10000(self):
        from BOTS.mexc import bot_engine
        source = inspect.getsource(bot_engine.BotEngine._update_balance)
        assert "10000.0" not in source
        assert "ACCOUNT_SIZE" in source

    def test_live_branch_untouched(self):
        from BOTS.mexc import bot_engine
        source = inspect.getsource(bot_engine.BotEngine._update_balance)
        assert "self._exchange.get_balance()" in source


class TestMtfConflictHardGate:
    """RFC V25 Item 4: conflito MTF isolado passa a reprovar sempre."""

    def test_old_combined_gate_removed(self):
        import main
        source = inspect.getsource(main)
        assert "Conflito MTF + Estrutura" not in source

    def test_new_standalone_gate_present(self):
        import main
        source = inspect.getsource(main)
        assert "Conflito MTF entre timeframes — REJEITADO" in source
        assert 'if is_mtf_conflict:' in source


class TestMathAuditorAccountLimitsIntegration:
    """RFC V25 Item 3: Math Auditor valida contra ACCOUNT_SIZE/LEVERAGE_MAX_USER reais."""

    def test_bullsusdt_symptom_now_blocked_with_real_env_limits(self):
        """Reproduz o sintoma reportado (nominal/margem incompativeis com a
        conta) usando as constantes reais do .env, nao valores arbitrarios."""
        phantom_balance = 10000.0  # saldo do bug antes da correcao (Item 1)
        entry, stop, tp1 = 1.0, 0.97, 1.06
        quantity = (phantom_balance * 0.02) / abs(entry - stop)

        result = InstitutionalMathAuditor.audit(
            entry_price=entry, stop_loss=stop, take_profit_1=tp1,
            quantity=quantity, balance=phantom_balance, leverage=1.0,
            risk_reward_expected=abs(tp1 - entry) / abs(entry - stop),
            account_capital=ACCOUNT_SIZE, max_leverage=LEVERAGE_MAX_USER,
        )
        assert not result.overall
        assert "MarginWithinCapital" in result.hard_fail_reason

    def test_consistent_signal_within_real_account_still_approved(self):
        """Sinal dimensionado corretamente contra o capital real (200) e
        dentro da alavancagem maxima (25) continua sendo aprovado — sem
        falso-positivo introduzido pelo novo gate."""
        real_balance = ACCOUNT_SIZE
        entry, stop, tp1 = 1.0, 0.97, 1.06
        quantity = (real_balance * 0.02) / abs(entry - stop)

        result = InstitutionalMathAuditor.audit(
            entry_price=entry, stop_loss=stop, take_profit_1=tp1,
            quantity=quantity, balance=real_balance, leverage=1.0,
            risk_reward_expected=abs(tp1 - entry) / abs(entry - stop),
            account_capital=ACCOUNT_SIZE, max_leverage=LEVERAGE_MAX_USER,
        )
        assert result.overall
        assert result.hard_fail_reason == ""

    def test_leverage_above_env_limit_blocked(self):
        result = InstitutionalMathAuditor.audit(
            entry_price=100, stop_loss=105, take_profit_1=90,
            quantity=1, balance=ACCOUNT_SIZE, leverage=LEVERAGE_MAX_USER + 1,
            risk_reward_expected=abs(90 - 100) / abs(100 - 105),
            account_capital=ACCOUNT_SIZE, max_leverage=LEVERAGE_MAX_USER,
        )
        assert not result.overall
        assert "LeverageWithinLimit" in result.hard_fail_reason
