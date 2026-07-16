import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import math
import pytest

from ENGINE.auditor.institutional_math_auditor import (
    InstitutionalMathAuditor, AuditResult, AuditCheck, MAX_DIVERGENCE_PCT,
)


class TestAuditCheck:
    def test_pass_status(self):
        c = AuditCheck("RR", True, 2.0, 2.0, 0.0)
        assert c.label == "PASS"
        assert c.passed

    def test_fail_status(self):
        c = AuditCheck("RR", False, 2.0, 1.5, 25.0)
        assert c.label == "FAIL"
        assert not c.passed


class TestAuditResult:
    def test_all_pass_true(self):
        r = AuditResult(
            checks=[AuditCheck("RR", True, 2.0, 2.0, 0.0)],
            overall=True,
        )
        assert r.all_pass

    def test_all_pass_false(self):
        r = AuditResult(
            checks=[AuditCheck("RR", False, 2.0, 1.5, 25.0)],
            overall=False,
        )
        assert not r.all_pass

    def test_log_report_includes_overall_pass(self):
        r = AuditResult(
            checks=[AuditCheck("RR", True, 2.0, 2.0, 0.0)],
            overall=True,
        )
        report = r.log_report()
        assert "PASS" in report

    def test_log_report_includes_overall_fail(self):
        r = AuditResult(
            checks=[AuditCheck("RR", False, 2.0, 1.5, 25.0)],
            overall=False,
            hard_fail_reason="MATH_VALIDATION_FAILED",
        )
        report = r.log_report()
        assert "FAIL" in report
        assert "MATH_VALIDATION_FAILED" in report

    def test_log_report_includes_diff_on_fail(self):
        r = AuditResult(
            checks=[AuditCheck("RR", False, 2.0, 1.5, 25.0)],
            overall=False,
        )
        report = r.log_report()
        assert "diff=25.0000%" in report


class TestPctDiff:
    def test_equal_values(self):
        assert InstitutionalMathAuditor._pct_diff(100, 100) == 0.0

    def test_zero_zero(self):
        assert InstitutionalMathAuditor._pct_diff(0, 0) == 0.0

    def test_zero_a(self):
        assert InstitutionalMathAuditor._pct_diff(0, 100) == 100.0

    def test_different_values(self):
        d = InstitutionalMathAuditor._pct_diff(100, 101)
        assert d == pytest.approx(1.0)

    def test_small_divergence(self):
        d = InstitutionalMathAuditor._pct_diff(100, 100.05)
        assert d == pytest.approx(0.05)


class TestAuditValidSignal:
    """Testa auditoria com dados reais do CATONUSDT."""

    @pytest.fixture
    def catonusdt_params(self):
        return {
            "entry_price": 936.615,
            "stop_loss": 943.1314,
            "take_profit_1": 923.58,
            "quantity": 46.037690,
            "balance": 10001.67,
            "leverage": 1.0,
            "risk_reward_expected": 2.00,
        }

    def test_audit_passes_valid_signal(self, catonusdt_params):
        result = InstitutionalMathAuditor.audit(**catonusdt_params)
        assert result.overall
        assert result.hard_fail_reason == ""
        assert result.all_pass

    def test_audit_correct_rr(self, catonusdt_params):
        result = InstitutionalMathAuditor.audit(**catonusdt_params)
        rr_check = [c for c in result.checks if c.name == "RR"][0]
        assert rr_check.passed
        assert rr_check.found == pytest.approx(2.00, abs=0.01)

    def test_audit_correct_nominal(self, catonusdt_params):
        result = InstitutionalMathAuditor.audit(**catonusdt_params)
        nominal_check = [c for c in result.checks if c.name == "Nominal"][0]
        expected = catonusdt_params["quantity"] * catonusdt_params["entry_price"]
        assert nominal_check.passed
        assert nominal_check.expected == pytest.approx(expected, abs=0.1)

    def test_audit_correct_max_loss(self, catonusdt_params):
        result = InstitutionalMathAuditor.audit(**catonusdt_params)
        loss_check = [c for c in result.checks if c.name == "MaxLoss"][0]
        stop_dist = abs(catonusdt_params["entry_price"] - catonusdt_params["stop_loss"])
        expected_loss = catonusdt_params["quantity"] * stop_dist
        assert loss_check.passed
        assert loss_check.expected == pytest.approx(expected_loss, abs=0.01)

    def test_audit_correct_expected_profit(self, catonusdt_params):
        result = InstitutionalMathAuditor.audit(**catonusdt_params)
        profit_check = [c for c in result.checks if c.name == "ExpectedProfit"][0]
        tp_dist = abs(catonusdt_params["entry_price"] - catonusdt_params["take_profit_1"])
        expected_profit = catonusdt_params["quantity"] * tp_dist
        assert profit_check.passed
        assert profit_check.expected == pytest.approx(expected_profit, abs=0.01)

    def test_audit_correct_return_on_asset(self, catonusdt_params):
        result = InstitutionalMathAuditor.audit(**catonusdt_params)
        roa_check = [c for c in result.checks if c.name == "ReturnOnAsset"][0]
        tp_dist = abs(catonusdt_params["entry_price"] - catonusdt_params["take_profit_1"])
        expected_roa = (tp_dist / catonusdt_params["entry_price"]) * 100
        assert roa_check.passed
        assert roa_check.expected == pytest.approx(expected_roa, abs=0.01)

    def test_audit_correct_return_on_margin(self, catonusdt_params):
        result = InstitutionalMathAuditor.audit(**catonusdt_params)
        rom_check = [c for c in result.checks if c.name == "ReturnOnMargin"][0]
        tp_dist = abs(catonusdt_params["entry_price"] - catonusdt_params["take_profit_1"])
        expected_profit = catonusdt_params["quantity"] * tp_dist
        margin = (catonusdt_params["quantity"] * catonusdt_params["entry_price"]) / catonusdt_params["leverage"]
        expected_rom = (expected_profit / margin) * 100
        assert rom_check.passed
        assert rom_check.expected == pytest.approx(expected_rom, abs=0.01)

    def test_audit_correct_return_on_equity(self, catonusdt_params):
        result = InstitutionalMathAuditor.audit(**catonusdt_params)
        roe_check = [c for c in result.checks if c.name == "ReturnOnEquity"][0]
        tp_dist = abs(catonusdt_params["entry_price"] - catonusdt_params["take_profit_1"])
        expected_profit = catonusdt_params["quantity"] * tp_dist
        expected_roe = (expected_profit / catonusdt_params["balance"]) * 100
        assert roe_check.passed
        assert roe_check.expected == pytest.approx(expected_roe, abs=0.01)

    def test_audit_correct_risk_percentage(self, catonusdt_params):
        result = InstitutionalMathAuditor.audit(**catonusdt_params)
        risk_check = [c for c in result.checks if c.name == "RiskPercentage"][0]
        stop_dist = abs(catonusdt_params["entry_price"] - catonusdt_params["stop_loss"])
        max_loss = catonusdt_params["quantity"] * stop_dist
        expected_risk = (max_loss / catonusdt_params["balance"]) * 100
        assert risk_check.passed
        assert risk_check.expected == pytest.approx(expected_risk, abs=0.01)

    def test_audit_coherence_qty_times_entry(self, catonusdt_params):
        result = InstitutionalMathAuditor.audit(**catonusdt_params)
        qty_entry_check = [c for c in result.checks if c.name == "QtyTimesEntryEqNominal"][0]
        assert qty_entry_check.passed
        expected = catonusdt_params["quantity"] * catonusdt_params["entry_price"]
        assert qty_entry_check.expected == pytest.approx(expected, abs=0.1)

    def test_audit_coherence_nominal_div_leverage(self, catonusdt_params):
        result = InstitutionalMathAuditor.audit(**catonusdt_params)
        ndl_check = [c for c in result.checks if c.name == "NominalDivLevEqMargin"][0]
        assert ndl_check.passed
        nominal = catonusdt_params["quantity"] * catonusdt_params["entry_price"]
        expected = nominal / catonusdt_params["leverage"]
        assert ndl_check.expected == pytest.approx(expected, abs=0.1)

    def test_audit_coherence_rr_from_profit_loss(self, catonusdt_params):
        result = InstitutionalMathAuditor.audit(**catonusdt_params)
        rr_pl_check = [c for c in result.checks if c.name == "RRFromProfitOverLoss"][0]
        assert rr_pl_check.passed

    def test_audit_with_leverage(self, catonusdt_params):
        params = catonusdt_params.copy()
        params["leverage"] = 5.0
        result = InstitutionalMathAuditor.audit(**params)
        assert result.overall
        margin_check = [c for c in result.checks if c.name == "Margin"][0]
        nominal = params["quantity"] * params["entry_price"]
        assert margin_check.expected == pytest.approx(nominal / 5.0, abs=0.1)


class TestAuditInvalidSignal:
    def test_zero_prices_fails(self):
        result = InstitutionalMathAuditor.audit(
            entry_price=0, stop_loss=0, take_profit_1=0,
            quantity=10, balance=1000, leverage=1, risk_reward_expected=2.0,
        )
        assert not result.overall
        assert "invalid prices" in result.hard_fail_reason

    def test_negative_prices_fails(self):
        result = InstitutionalMathAuditor.audit(
            entry_price=-100, stop_loss=-90, take_profit_1=-110,
            quantity=10, balance=1000, leverage=1, risk_reward_expected=2.0,
        )
        assert not result.overall

    def test_rr_mismatch_fails(self):
        result = InstitutionalMathAuditor.audit(
            entry_price=100, stop_loss=105, take_profit_1=90,
            quantity=10, balance=1000, leverage=1, risk_reward_expected=99.0,
        )
        assert not result.overall
        rr_check = [c for c in result.checks if c.name == "RR"][0]
        assert not rr_check.passed

    def test_stop_distance_zero_fails_rr(self):
        result = InstitutionalMathAuditor.audit(
            entry_price=100, stop_loss=100, take_profit_1=90,
            quantity=10, balance=1000, leverage=1, risk_reward_expected=2.0,
        )
        assert result.overall is False
        rr_check = [c for c in result.checks if c.name == "RR"][0]
        assert not rr_check.passed

    def test_zero_balance_zero_leverage_margin_checks_pass(self):
        result = InstitutionalMathAuditor.audit(
            entry_price=100, stop_loss=105, take_profit_1=90,
            quantity=10, balance=0, leverage=0,
            risk_reward_expected=2.0,
        )
        assert result.overall
        margin_check = [c for c in result.checks if c.name == "Margin"][0]
        assert margin_check.expected == 0.0
        assert margin_check.passed


class TestEdgeCases:
    def test_very_small_prices(self):
        result = InstitutionalMathAuditor.audit(
            entry_price=0.000001, stop_loss=0.000002, take_profit_1=0.0000005,
            quantity=1000000, balance=100, leverage=1,
            risk_reward_expected=0.5,
        )
        assert result.overall

    def test_very_large_prices(self):
        result = InstitutionalMathAuditor.audit(
            entry_price=100000, stop_loss=105000, take_profit_1=90000,
            quantity=0.001, balance=100, leverage=1,
            risk_reward_expected=2.0,
        )
        assert result.overall

    def test_high_leverage(self):
        result = InstitutionalMathAuditor.audit(
            entry_price=100, stop_loss=102, take_profit_1=94,
            quantity=50, balance=1000, leverage=100,
            risk_reward_expected=3.0,
        )
        assert result.overall
        margin_check = [c for c in result.checks if c.name == "Margin"][0]
        expected_margin = (50 * 100) / 100
        assert margin_check.expected == pytest.approx(expected_margin, abs=0.01)


class TestMaxDivergence:
    def test_exact_match_passes(self):
        d = InstitutionalMathAuditor._pct_diff(100.0, 100.0)
        assert d <= MAX_DIVERGENCE_PCT

    def test_within_tolerance_passes(self):
        d = InstitutionalMathAuditor._pct_diff(100.0, 100.05)
        assert d <= MAX_DIVERGENCE_PCT

    def test_exceeds_tolerance_fails(self):
        d = InstitutionalMathAuditor._pct_diff(100.0, 102.5)
        assert d > MAX_DIVERGENCE_PCT

    def test_boundary_at_tolerance(self):
        d = InstitutionalMathAuditor._pct_diff(100.0, 100.10)
        assert d == pytest.approx(0.10)

    def test_rr_small_divergence_passes(self):
        stop_dist = 6.5164
        tp_dist = 13.0350
        rr = tp_dist / stop_dist
        result = InstitutionalMathAuditor.audit(
            entry_price=936.615, stop_loss=943.1314, take_profit_1=923.58,
            quantity=46.037690, balance=10001.67, leverage=1.0,
            risk_reward_expected=rr,
        )
        assert result.overall


class TestCheckCoverage:
    """Verifica que todos os checks esperados estao presentes."""

    EXPECTED_CHECKS = [
        "RR",
        "StopDistance",
        "TPDistance",
        "Nominal",
        "Margin",
        "MaxLoss",
        "ExpectedProfit",
        "ReturnOnAsset",
        "ReturnOnMargin",
        "ReturnOnEquity",
        "RiskPercentage",
        "CapitalUsed",
        "QtyTimesEntryEqNominal",
        "NominalDivLevEqMargin",
        "QtyTimesStopDistEqMaxLoss",
        "QtyTimesTPDistEqProfit",
        "RRFromProfitOverLoss",
    ]

    def test_all_checks_present(self):
        result = InstitutionalMathAuditor.audit(
            entry_price=100, stop_loss=105, take_profit_1=90,
            quantity=10, balance=1000, leverage=1,
            risk_reward_expected=2.0,
        )
        check_names = {c.name for c in result.checks}
        for expected in self.EXPECTED_CHECKS:
            assert expected in check_names, f"Check '{expected}' not found in audit"

    def test_total_checks_count(self):
        result = InstitutionalMathAuditor.audit(
            entry_price=100, stop_loss=105, take_profit_1=90,
            quantity=10, balance=1000, leverage=1,
            risk_reward_expected=2.0,
        )
        assert len(result.checks) == len(self.EXPECTED_CHECKS)


class TestAuditResultLog:
    def test_log_includes_all_checks(self):
        result = InstitutionalMathAuditor.audit(
            entry_price=100, stop_loss=105, take_profit_1=90,
            quantity=10, balance=1000, leverage=1,
            risk_reward_expected=2.0,
        )
        report = result.log_report()
        for c in result.checks:
            assert c.name in report


class TestAccountCapitalAndLeverageGate:
    """RFC V25: Hard Gate Financeiro real contra limites de conta."""

    def test_checks_absent_when_limits_not_provided(self):
        result = InstitutionalMathAuditor.audit(
            entry_price=100, stop_loss=105, take_profit_1=90,
            quantity=10, balance=1000, leverage=1,
            risk_reward_expected=2.0,
        )
        check_names = {c.name for c in result.checks}
        assert "MarginWithinCapital" not in check_names
        assert "LeverageWithinLimit" not in check_names

    def test_margin_within_capital_passes(self):
        result = InstitutionalMathAuditor.audit(
            entry_price=100, stop_loss=105, take_profit_1=90,
            quantity=1, balance=200, leverage=1,
            risk_reward_expected=2.0,
            account_capital=200, max_leverage=25,
        )
        margin_check = [c for c in result.checks if c.name == "MarginWithinCapital"][0]
        assert margin_check.passed
        assert result.overall

    def test_margin_exceeds_capital_blocks(self):
        # Nominal = 50 * 100 = 5000, leverage 1 -> margem 5000, capital configurado 200
        result = InstitutionalMathAuditor.audit(
            entry_price=100, stop_loss=105, take_profit_1=90,
            quantity=50, balance=10000, leverage=1,
            risk_reward_expected=2.0,
            account_capital=200, max_leverage=25,
        )
        margin_check = [c for c in result.checks if c.name == "MarginWithinCapital"][0]
        assert not margin_check.passed
        assert not result.overall
        assert "MarginWithinCapital" in result.hard_fail_reason

    def test_leverage_within_limit_passes(self):
        result = InstitutionalMathAuditor.audit(
            entry_price=100, stop_loss=105, take_profit_1=90,
            quantity=1, balance=200, leverage=25,
            risk_reward_expected=2.0,
            account_capital=200, max_leverage=25,
        )
        leverage_check = [c for c in result.checks if c.name == "LeverageWithinLimit"][0]
        assert leverage_check.passed
        assert result.overall

    def test_leverage_exceeds_limit_blocks(self):
        result = InstitutionalMathAuditor.audit(
            entry_price=100, stop_loss=105, take_profit_1=90,
            quantity=1, balance=200, leverage=50,
            risk_reward_expected=2.0,
            account_capital=200, max_leverage=25,
        )
        leverage_check = [c for c in result.checks if c.name == "LeverageWithinLimit"][0]
        assert not leverage_check.passed
        assert not result.overall
        assert "LeverageWithinLimit" in result.hard_fail_reason

    def test_bullsusdt_style_oversized_signal_blocks(self):
        # Reproduz o sintoma reportado: saldo fantasma (10000) usado para
        # dimensionar quantidade, capital real configurado = 200.
        real_balance_used_by_bug = 10000.0
        entry, stop, tp1 = 1.0, 0.97, 1.06
        quantity = (real_balance_used_by_bug * 0.02) / abs(entry - stop)
        result = InstitutionalMathAuditor.audit(
            entry_price=entry, stop_loss=stop, take_profit_1=tp1,
            quantity=quantity, balance=real_balance_used_by_bug, leverage=1.0,
            risk_reward_expected=abs(tp1 - entry) / abs(entry - stop),
            account_capital=200, max_leverage=25,
        )
        assert not result.overall
        assert "MarginWithinCapital" in result.hard_fail_reason
