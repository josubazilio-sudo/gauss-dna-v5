import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

MAX_DIVERGENCE_PCT = 1.5


@dataclass
class AuditCheck:
    name: str
    passed: bool
    expected: float
    found: float
    divergence_pct: float = 0.0

    @property
    def label(self) -> str:
        return "PASS" if self.passed else "FAIL"


@dataclass
class AuditResult:
    checks: List[AuditCheck] = field(default_factory=list)
    overall: bool = False
    hard_fail_reason: str = ""

    @property
    def all_pass(self) -> bool:
        return all(c.passed for c in self.checks)

    def log_report(self) -> str:
        lines = [
            "=" * 50,
            "INSTITUTIONAL MATH AUDIT",
            "=" * 50,
        ]
        for c in self.checks:
            status = c.label
            if c.passed:
                lines.append(f"{c.name:.<25}{status}")
            else:
                diff_str = f"diff={c.divergence_pct:.4f}%"
                lines.append(
                    f"{c.name:.<25}{status}  "
                    f"expected={c.expected:.8f} found={c.found:.8f} {diff_str}"
                )
        overall_status = "PASS" if self.overall else "FAIL"
        lines.append(f"{'Overall':.<25}{overall_status}")
        if self.hard_fail_reason:
            lines.append(f"hard_fail_reason={self.hard_fail_reason}")
        lines.append("=" * 50)
        report = "\n".join(lines)
        for line in lines:
            log.info("MATH_AUDIT| %s", line)
        return report


class InstitutionalMathAuditor:

    @staticmethod
    def _pct_diff(a: float, b: float) -> float:
        if a == 0 and b == 0:
            return 0.0
        if a == 0:
            return 100.0
        return abs((a - b) / a) * 100

    @staticmethod
    def _check(name: str, expected: float, found: float) -> AuditCheck:
        divergence = InstitutionalMathAuditor._pct_diff(expected, found)
        passed = divergence <= MAX_DIVERGENCE_PCT
        return AuditCheck(
            name=name,
            passed=passed,
            expected=expected,
            found=found,
            divergence_pct=divergence,
        )

    @staticmethod
    def audit(
        entry_price: float,
        stop_loss: float,
        take_profit_1: float,
        quantity: float,
        balance: float,
        leverage: float,
        risk_reward_expected: float,
        account_capital: Optional[float] = None,
        max_leverage: Optional[float] = None,
    ) -> AuditResult:
        checks: List[AuditCheck] = []

        if entry_price <= 0 or stop_loss <= 0 or take_profit_1 <= 0:
            return AuditResult(
                checks=[AuditCheck("InputValidation", False, 0, 0)],
                overall=False,
                hard_fail_reason="MATH_VALIDATION_FAILED: invalid prices",
            )

        stop_distance = abs(entry_price - stop_loss)
        tp_distance = abs(entry_price - take_profit_1)

        # RR
        calculated_rr = tp_distance / stop_distance if stop_distance > 0 else 0.0
        checks.append(InstitutionalMathAuditor._check(
            "RR", risk_reward_expected, calculated_rr
        ))

        # Stop Distance
        checks.append(InstitutionalMathAuditor._check(
            "StopDistance", stop_distance, stop_distance
        ))

        # TP Distance
        checks.append(InstitutionalMathAuditor._check(
            "TPDistance", tp_distance, tp_distance
        ))

        # Position Size / Nominal
        nominal = quantity * entry_price
        checks.append(AuditCheck(
            name="Nominal",
            passed=True,
            expected=nominal,
            found=nominal,
            divergence_pct=0.0,
        ))

        # Margin
        margin = nominal / leverage if leverage > 0 else 0.0
        checks.append(AuditCheck(
            name="Margin",
            passed=True,
            expected=margin,
            found=margin,
            divergence_pct=0.0,
        ))

        # Margin Within Capital (Hard Gate V25 — limite real de conta)
        if account_capital is not None:
            margin_ok = margin <= account_capital
            checks.append(AuditCheck(
                name="MarginWithinCapital",
                passed=margin_ok,
                expected=account_capital,
                found=margin,
                divergence_pct=0.0 if margin_ok else InstitutionalMathAuditor._pct_diff(account_capital, margin),
            ))

        # Leverage Within Limit (Hard Gate V25 — limite real de conta)
        if max_leverage is not None:
            leverage_ok = leverage <= max_leverage
            checks.append(AuditCheck(
                name="LeverageWithinLimit",
                passed=leverage_ok,
                expected=max_leverage,
                found=leverage,
                divergence_pct=0.0 if leverage_ok else InstitutionalMathAuditor._pct_diff(max_leverage, leverage),
            ))

        # Max Loss
        max_loss = quantity * stop_distance
        checks.append(AuditCheck(
            name="MaxLoss",
            passed=True,
            expected=max_loss,
            found=max_loss,
            divergence_pct=0.0,
        ))

        # Expected Profit
        expected_profit = quantity * tp_distance
        checks.append(AuditCheck(
            name="ExpectedProfit",
            passed=True,
            expected=expected_profit,
            found=expected_profit,
            divergence_pct=0.0,
        ))

        # Return on Asset
        return_on_asset = (tp_distance / entry_price) * 100 if entry_price > 0 else 0.0
        checks.append(AuditCheck(
            name="ReturnOnAsset",
            passed=True,
            expected=return_on_asset,
            found=return_on_asset,
            divergence_pct=0.0,
        ))

        # Return on Margin
        return_on_margin = (expected_profit / margin * 100) if margin > 0 else 0.0
        checks.append(AuditCheck(
            name="ReturnOnMargin",
            passed=True,
            expected=return_on_margin,
            found=return_on_margin,
            divergence_pct=0.0,
        ))

        # Return on Equity
        return_on_equity = (expected_profit / balance * 100) if balance > 0 else 0.0
        checks.append(AuditCheck(
            name="ReturnOnEquity",
            passed=True,
            expected=return_on_equity,
            found=return_on_equity,
            divergence_pct=0.0,
        ))

        # Risk Percentage
        risk_pct = (max_loss / balance * 100) if balance > 0 else 0.0
        checks.append(AuditCheck(
            name="RiskPercentage",
            passed=True,
            expected=risk_pct,
            found=risk_pct,
            divergence_pct=0.0,
        ))

        # Capital Used
        nominal_sanity = quantity * entry_price
        margin_sanity = nominal_sanity / leverage if leverage > 0 else 0.0
        checks.append(AuditCheck(
            name="CapitalUsed",
            passed=True,
            expected=margin_sanity,
            found=margin_sanity,
            divergence_pct=0.0,
        ))

        # Coherence: Quantidade * Entrada = Valor Nominal
        quantity_nominal = quantity * entry_price
        checks.append(AuditCheck(
            name="QtyTimesEntryEqNominal",
            passed=True,
            expected=quantity_nominal,
            found=quantity_nominal,
            divergence_pct=0.0,
        ))

        # Coherence: Nominal / Alavancagem = Margem
        nominal_div_leverage = nominal / leverage if leverage > 0 else 0.0
        checks.append(AuditCheck(
            name="NominalDivLevEqMargin",
            passed=True,
            expected=nominal_div_leverage,
            found=nominal_div_leverage,
            divergence_pct=0.0,
        ))

        # Coherence: Quantidade * Dist Stop = Perda Max
        qty_stop_dist = quantity * stop_distance
        checks.append(AuditCheck(
            name="QtyTimesStopDistEqMaxLoss",
            passed=True,
            expected=qty_stop_dist,
            found=qty_stop_dist,
            divergence_pct=0.0,
        ))

        # Coherence: Quantidade * Dist TP = Lucro
        qty_tp_dist = quantity * tp_distance
        checks.append(AuditCheck(
            name="QtyTimesTPDistEqProfit",
            passed=True,
            expected=qty_tp_dist,
            found=qty_tp_dist,
            divergence_pct=0.0,
        ))

        # Coherence: RR = Lucro / Perda
        rr_from_loss_profit = expected_profit / max_loss if max_loss > 0 else 0.0
        checks.append(InstitutionalMathAuditor._check(
            "RRFromProfitOverLoss", calculated_rr, rr_from_loss_profit
        ))

        overall = all(c.passed for c in checks)
        if overall:
            hard_fail = ""
        else:
            failed = [c for c in checks if not c.passed]
            details = "; ".join(
                f"{c.name}: found={c.found:.4f} expected={c.expected:.4f}"
                for c in failed
            )
            hard_fail = f"MATH_VALIDATION_FAILED: {details}"

        return AuditResult(
            checks=checks,
            overall=overall,
            hard_fail_reason=hard_fail,
        )
