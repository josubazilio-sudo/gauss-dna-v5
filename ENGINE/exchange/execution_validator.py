import logging
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


@dataclass
class ExchangeSymbolInfo:
    symbol: str
    tick_size: float = 0.0
    step_size: float = 0.0
    min_qty: float = 0.0
    max_qty: float = 0.0
    min_notional: float = 0.0
    max_notional: float = 0.0
    price_precision: int = 0
    qty_precision: int = 0
    min_leverage: int = 1
    max_leverage: int = 125
    is_active: bool = True
    is_futures: bool = True
    contract_status: str = "TRADING"
    maintenance_margin_rate: float = 0.005
    taker_fee_rate: float = 0.0006
    maker_fee_rate: float = 0.0002

    @staticmethod
    def from_mexc_symbol(raw: dict) -> "ExchangeSymbolInfo":
        filters = {f["filterType"]: f for f in raw.get("filters", [])}
        pf = filters.get("PRICE_FILTER", {})
        lf = filters.get("LOT_SIZE", {})
        mn = filters.get("MIN_NOTIONAL", {})
        mp = filters.get("MAX_POSITION", {})
        return ExchangeSymbolInfo(
            symbol=raw.get("symbol", ""),
            tick_size=float(pf.get("tickSize", 0)),
            step_size=float(lf.get("stepSize", 0)),
            min_qty=float(lf.get("minQty", 0)),
            max_qty=float(lf.get("maxQty", 0)),
            min_notional=float(mn.get("minNotional", 0)),
            max_notional=float(mp.get("maxPosition", 0)) if mp else 0.0,
            price_precision=raw.get("pricePrecision", 0) if "pricePrecision" in raw
            else _precision_from_str(pf.get("tickSize", "")),
            qty_precision=raw.get("quantityPrecision", 0) if "quantityPrecision" in raw
            else _precision_from_str(lf.get("stepSize", "")),
            is_active=raw.get("status", "") == "TRADING",
            is_futures="FUTURES" in raw.get("permissions", []),
            contract_status=raw.get("status", ""),
        )

    @staticmethod
    def from_binance_symbol(raw: dict) -> "ExchangeSymbolInfo":
        filters = {f["filterType"]: f for f in raw.get("filters", [])}
        pf = filters.get("PRICE_FILTER", {})
        lf = filters.get("LOT_SIZE", {})
        mn = filters.get("MIN_NOTIONAL", {})
        mp = filters.get("MAX_POSITION", {}) or {}
        return ExchangeSymbolInfo(
            symbol=raw.get("symbol", ""),
            tick_size=float(pf.get("tickSize", 0)),
            step_size=float(lf.get("stepSize", 0)),
            min_qty=float(lf.get("minQty", 0)),
            max_qty=float(lf.get("maxQty", 0)),
            min_notional=float(mn.get("minNotional", 0)),
            max_notional=float(mp.get("maxPosition", 0)) if mp else 0.0,
            price_precision=raw.get("quotePrecision", 0) if "quotePrecision" in raw
            else _precision_from_str(pf.get("tickSize", "")),
            qty_precision=raw.get("baseAssetPrecision", 0) if "baseAssetPrecision" in raw
            else _precision_from_str(lf.get("stepSize", "")),
            is_active=raw.get("status", "") == "TRADING",
            is_futures=raw.get("contractType", "") in ("PERPETUAL", "CURRENT_QUARTER", "NEXT_QUARTER"),
            contract_status=raw.get("status", ""),
        )

    @staticmethod
    def from_bybit_symbol(raw: dict) -> "ExchangeSymbolInfo":
        return ExchangeSymbolInfo(
            symbol=raw.get("symbol", ""),
            tick_size=float(raw.get("priceFilter", {}).get("tickSize", 0)),
            step_size=float(raw.get("lotSizeFilter", {}).get("qtyStep", 0)),
            min_qty=float(raw.get("lotSizeFilter", {}).get("minOrderQty", 0)),
            max_qty=float(raw.get("lotSizeFilter", {}).get("maxOrderQty", 0)),
            min_notional=float(raw.get("lotSizeFilter", {}).get("minOrderAmt", 0)),
            max_notional=float(raw.get("lotSizeFilter", {}).get("maxOrderAmt", 0)) if "maxOrderAmt" in raw.get("lotSizeFilter", {}) else 0.0,
            price_precision=_precision_from_str(raw.get("priceFilter", {}).get("tickSize", "")),
            qty_precision=_precision_from_str(raw.get("lotSizeFilter", {}).get("qtyStep", "")),
            is_active=raw.get("status", "") == "Trading",
            is_futures=raw.get("contractType", "") in ("LinearPerpetual", "InversePerpetual"),
            contract_status=raw.get("status", ""),
        )


def _precision_from_str(s: str) -> int:
    s = s.rstrip("0").rstrip(".")
    if "." not in s:
        return 0
    return len(s.split(".")[1])


@dataclass
class ValidationCheckItem:
    name: str
    passed: bool
    expected: str = ""
    found: str = ""
    difference: str = ""
    technical_reason: str = ""

    @property
    def label(self) -> str:
        return "PASS" if self.passed else "FAIL"


@dataclass
class ExecutionValidationResult:
    checks: List[ValidationCheckItem] = field(default_factory=list)
    overall: bool = False
    hard_fail_reason: str = ""
    tick_size: float = 0.0
    step_size: float = 0.0
    liquidation_price: float = 0.0
    liquidation_risk: bool = False
    maker_fee: float = 0.0
    taker_fee: float = 0.0
    funding_estimate: float = 0.0
    slippage_cost: float = 0.0
    net_rr: float = 0.0
    net_profit: float = 0.0
    net_loss: float = 0.0
    total_fees: float = 0.0
    position_value: float = 0.0
    margin_required: float = 0.0
    margin_available: float = 0.0

    def log_report(self) -> str:
        lines = [
            "=" * 50,
            "EXCHANGE EXECUTION VALIDATOR",
            "=" * 50,
        ]
        for c in self.checks:
            status = c.label
            if c.passed:
                lines.append(f"{c.name:.<30}{status}")
            else:
                extra = ""
                if c.expected:
                    extra += f" expected={c.expected}"
                if c.found:
                    extra += f" found={c.found}"
                if c.difference:
                    extra += f" diff={c.difference}"
                if c.technical_reason:
                    extra += f" reason={c.technical_reason}"
                lines.append(f"{c.name:.<30}{status}{extra}")
        liq_status = "OK" if not self.liquidation_risk else "RISK"
        liq_label = "PASS" if not self.liquidation_risk else "FAIL"
        lines.append(f"{'Liquidation Risk':.<30}{liq_label}  liq_price={self.liquidation_price:.8f} status={liq_status}")
        fee_label = "PASS" if self.taker_fee >= 0 else "FAIL"
        lines.append(f"{'Fees':.<30}{fee_label}  maker={self.maker_fee:.8f} taker={self.taker_fee:.8f} total={self.total_fees:.8f}")
        rr_label = "PASS" if self.net_rr >= 0 else "FAIL"
        lines.append(f"{'Net RR':.<30}{rr_label}  net_rr={self.net_rr:.4f} net_profit={self.net_profit:.8f} net_loss={self.net_loss:.8f}")
        overall_label = "PASS" if self.overall else "FAIL"
        lines.append(f"{'Execution':.<30}{overall_label}")
        if self.hard_fail_reason:
            lines.append(f"hard_fail_reason={self.hard_fail_reason}")
        lines.append("=" * 50)
        report = "\n".join(lines)
        for line in lines:
            log.info("EXEC_VALIDATOR| %s", line)
        return report


class ExchangeExecutionValidator:

    def __init__(
        self,
        symbol_info: ExchangeSymbolInfo,
        auto_round_prices: bool = False,
        auto_round_quantity: bool = False,
        block_invalid: bool = True,
        tolerance: float = 0.000001,
        slippage_rate: float = 0.0005,
        funding_rate_estimate: float = 0.0001,
    ):
        self._info = symbol_info
        self._auto_round_prices = auto_round_prices
        self._auto_round_quantity = auto_round_quantity
        self._block_invalid = block_invalid
        self._tolerance = tolerance
        self._slippage_rate = slippage_rate
        self._funding_rate_estimate = funding_rate_estimate

    @property
    def symbol(self) -> str:
        return self._info.symbol

    def round_price(self, price: float) -> float:
        ts = self._info.tick_size
        if ts <= 0:
            return price
        d_price = Decimal(str(price))
        d_ts = Decimal(str(ts))
        units = (d_price / d_ts).to_integral_value(rounding=ROUND_HALF_UP)
        return float(units * d_ts)

    def round_quantity(self, quantity: float) -> float:
        ss = self._info.step_size
        if ss <= 0:
            return quantity
        d_qty = Decimal(str(quantity))
        d_ss = Decimal(str(ss))
        units = (d_qty / d_ss).to_integral_value(rounding=ROUND_HALF_UP)
        return float(units * d_ss)

    def _check_tick_size(self, price: float, label: str) -> Optional[ValidationCheckItem]:
        ts = self._info.tick_size
        if ts <= 0:
            return None
        remainder = abs(price % ts)
        aligned = remainder < self._tolerance or abs(remainder - ts) < self._tolerance
        if not aligned and self._auto_round_prices:
            return ValidationCheckItem(
                name=f"TickSize_{label}", passed=True,
                expected=f"{price:.8f}",
                found=f"{self.round_price(price):.8f}",
                technical_reason="auto_rounded",
            )
        if not aligned:
            rounded = self.round_price(price)
            return ValidationCheckItem(
                name=f"TickSize_{label}", passed=False,
                expected=f"multiple of {ts}",
                found=f"{price:.8f}",
                difference=f"{remainder:.8f}",
                technical_reason=f"not aligned to tick_size; nearest={rounded:.8f}",
            )
        return ValidationCheckItem(
            name=f"TickSize_{label}", passed=True,
            expected=f"aligned to {ts}", found=f"{price:.8f}",
        )

    def _check_step_size(self, quantity: float) -> Optional[ValidationCheckItem]:
        ss = self._info.step_size
        if ss <= 0:
            return None
        remainder = abs(quantity % ss)
        aligned = remainder < self._tolerance or abs(remainder - ss) < self._tolerance
        if not aligned and self._auto_round_quantity:
            return ValidationCheckItem(
                name="StepSize", passed=True,
                expected=f"{quantity:.8f}",
                found=f"{self.round_quantity(quantity):.8f}",
                technical_reason="auto_rounded",
            )
        if not aligned:
            return ValidationCheckItem(
                name="StepSize", passed=False,
                expected=f"multiple of {ss}",
                found=f"{quantity:.8f}",
                difference=f"{remainder:.8f}",
                technical_reason="not aligned to step_size",
            )
        return ValidationCheckItem(
            name="StepSize", passed=True,
            expected=f"aligned to {ss}", found=f"{quantity:.8f}",
        )

    def _check_price_precision(self, price: float, label: str) -> Optional[ValidationCheckItem]:
        prec = self._info.price_precision
        if prec <= 0:
            return None
        check_price = self.round_price(price) if self._auto_round_prices else price
        price_str = f"{check_price:.10f}"
        decimal_part = price_str.split(".")[1] if "." in price_str else ""
        actual_prec = len(decimal_part.rstrip("0")) if "." in price_str else 0
        if actual_prec > prec:
            return ValidationCheckItem(
                name=f"PricePrecision_{label}", passed=False,
                expected=f"max {prec} decimals",
                found=f"{check_price:.10f}",
                difference=f"{actual_prec} > {prec}",
                technical_reason=f"precision overflow ({actual_prec} decimals, max {prec})",
            )
        return ValidationCheckItem(
            name=f"PricePrecision_{label}", passed=True,
            expected=f"<= {prec} decimals", found=f"{check_price:.10f}",
        )

    def _check_qty_precision(self, quantity: float) -> Optional[ValidationCheckItem]:
        prec = self._info.qty_precision
        if prec <= 0:
            return None
        check_qty = self.round_quantity(quantity) if self._auto_round_quantity else quantity
        qty_str = f"{check_qty:.10f}"
        decimal_part = qty_str.split(".")[1] if "." in qty_str else ""
        actual_prec = len(decimal_part.rstrip("0")) if "." in qty_str else 0
        if actual_prec > prec:
            return ValidationCheckItem(
                name="QtyPrecision", passed=False,
                expected=f"max {prec} decimals",
                found=f"{check_qty:.10f}",
                difference=f"{actual_prec} > {prec}",
                technical_reason=f"precision overflow ({actual_prec} decimals, max {prec})",
            )
        return ValidationCheckItem(
            name="QtyPrecision", passed=True,
            expected=f"<= {prec} decimals", found=f"{check_qty:.10f}",
        )

    def _check_lot_size(self, quantity: float) -> Optional[ValidationCheckItem]:
        min_q = self._info.min_qty
        max_q = self._info.max_qty
        if min_q <= 0 and max_q <= 0:
            return None
        if min_q > 0 and quantity < min_q - self._tolerance:
            return ValidationCheckItem(
                name="LotSize", passed=False,
                expected=f">= {min_q}", found=f"{quantity:.8f}",
                difference=f"{min_q - quantity:.8f}",
                technical_reason=f"below minimum lot size",
            )
        if max_q > 0 and quantity > max_q + self._tolerance:
            return ValidationCheckItem(
                name="LotSize", passed=False,
                expected=f"<= {max_q}", found=f"{quantity:.8f}",
                difference=f"{quantity - max_q:.8f}",
                technical_reason=f"above maximum lot size",
            )
        return ValidationCheckItem(
            name="LotSize", passed=True,
            expected=f"[{min_q}, {max_q}]", found=f"{quantity:.8f}",
        )

    def _check_min_notional(self, nominal: float) -> Optional[ValidationCheckItem]:
        mn = self._info.min_notional
        if mn <= 0:
            return None
        if nominal < mn - self._tolerance:
            return ValidationCheckItem(
                name="MinNotional", passed=False,
                expected=f">= {mn}", found=f"{nominal:.8f}",
                difference=f"{mn - nominal:.8f}",
                technical_reason=f"nominal {nominal:.8f} below min_notional {mn}",
            )
        return ValidationCheckItem(
            name="MinNotional", passed=True,
            expected=f">= {mn}", found=f"{nominal:.8f}",
        )

    def _check_max_notional(self, nominal: float) -> Optional[ValidationCheckItem]:
        mx = self._info.max_notional
        if mx <= 0:
            return None
        if nominal > mx + self._tolerance:
            return ValidationCheckItem(
                name="MaxNotional", passed=False,
                expected=f"<= {mx}", found=f"{nominal:.8f}",
                difference=f"{nominal - mx:.8f}",
                technical_reason=f"nominal {nominal:.8f} above max_notional {mx}",
            )
        return ValidationCheckItem(
            name="MaxNotional", passed=True,
            expected=f"<= {mx}", found=f"{nominal:.8f}",
        )

    def _check_leverage(self, leverage: float) -> Optional[ValidationCheckItem]:
        min_l = self._info.min_leverage
        max_l = self._info.max_leverage
        if leverage < min_l - self._tolerance:
            return ValidationCheckItem(
                name="Leverage", passed=False,
                expected=f">= {min_l}", found=f"{leverage:.2f}x",
                difference=f"{min_l - leverage:.2f}",
                technical_reason=f"below minimum leverage {min_l}x",
            )
        if leverage > max_l + self._tolerance:
            return ValidationCheckItem(
                name="Leverage", passed=False,
                expected=f"<= {max_l}", found=f"{leverage:.2f}x",
                difference=f"{leverage - max_l:.2f}",
                technical_reason=f"above maximum leverage {max_l}x",
            )
        return ValidationCheckItem(
            name="Leverage", passed=True,
            expected=f"[{min_l}, {max_l}]", found=f"{leverage:.2f}x",
        )

    def _check_active(self) -> Optional[ValidationCheckItem]:
        if not self._info.is_active:
            return ValidationCheckItem(
                name="ContractStatus", passed=False,
                expected="TRADING", found=self._info.contract_status,
                technical_reason="contract not active",
            )
        return ValidationCheckItem(
            name="ContractStatus", passed=True,
            expected="TRADING", found=self._info.contract_status,
        )

    def _calculate_liquidation(
        self, entry_price: float, leverage: float, direction: str
    ) -> float:
        mmr = self._info.maintenance_margin_rate
        if direction.upper() == "SHORT":
            return entry_price * (1.0 + 1.0 / max(leverage, 0.01) - mmr)
        return entry_price * (1.0 - 1.0 / max(leverage, 0.01) + mmr)

    def _check_liquidation_risk(
        self, entry_price: float, stop_loss: float, leverage: float, direction: str
    ) -> Tuple[ValidationCheckItem, float, bool]:
        liq = self._calculate_liquidation(entry_price, leverage, direction)
        is_risk = False
        if direction.upper() == "SHORT" and liq <= stop_loss + self._tolerance:
            is_risk = True
        elif direction.upper() == "LONG" and liq >= stop_loss - self._tolerance:
            is_risk = True
        risk_label = f"liquidation={liq:.8f} stop={stop_loss:.8f}"
        if is_risk:
            return (
                ValidationCheckItem(
                    name="LiquidationRisk", passed=False,
                    expected=f"liq beyond stop_loss",
                    found=f"liq={liq:.8f} stop={stop_loss:.8f}",
                    technical_reason=f"liquidation before stop_loss",
                ),
                liq,
                is_risk,
            )
        return (
            ValidationCheckItem(
                name="LiquidationRisk", passed=True,
                expected=f"safe", found=risk_label,
            ),
            liq,
            is_risk,
        )

    def _calculate_fees(
        self, quantity: float, entry_price: float,
        stop_loss: float, take_profit_1: float,
    ) -> Tuple[float, float, float, float]:
        pos_val = quantity * entry_price
        maker = pos_val * self._info.maker_fee_rate
        taker = pos_val * self._info.taker_fee_rate
        total = taker * 2
        return maker, taker, total, pos_val

    def _check_margin(
        self, nominal: float, leverage: float, balance: float
    ) -> Optional[ValidationCheckItem]:
        margin = nominal / max(leverage, 0.01)
        if margin >= balance - self._tolerance:
            return ValidationCheckItem(
                name="Margin", passed=False,
                expected=f"margin < balance ({balance:.8f})",
                found=f"margin={margin:.8f}",
                difference=f"{margin - balance:.8f}",
                technical_reason=f"margin required exceeds available balance",
            )
        return ValidationCheckItem(
            name="Margin", passed=True,
            expected=f"margin < balance ({balance:.8f})",
            found=f"margin={margin:.8f}",
        )

    def validate(
        self,
        entry_price: float,
        stop_loss: float,
        take_profit_1: float,
        take_profit_2: float = 0.0,
        quantity: float = 0.0,
        balance: float = 0.0,
        leverage: float = 1.0,
        direction: str = "LONG",
        trailing_stop: Optional[float] = None,
    ) -> ExecutionValidationResult:
        checks: List[ValidationCheckItem] = []

        if entry_price <= 0 or stop_loss <= 0 or take_profit_1 <= 0 or quantity <= 0:
            return ExecutionValidationResult(
                checks=[ValidationCheckItem(
                    name="InputValidation", passed=False,
                    technical_reason="invalid or zero input values",
                )],
                overall=False,
                hard_fail_reason="EXCHANGE_VALIDATION_FAILED: invalid inputs",
            )

        # Contract Active
        active_check = self._check_active()
        if active_check:
            checks.append(active_check)

        positional_value = quantity * entry_price

        # Price checks
        for price, label in [
            (entry_price, "Entry"),
            (stop_loss, "Stop"),
            (take_profit_1, "TP1"),
            (take_profit_2, "TP2"),
        ]:
            if price <= 0:
                continue
            ts = self._check_tick_size(price, label)
            if ts:
                checks.append(ts)
            pp = self._check_price_precision(price, label)
            if pp:
                checks.append(pp)

        if trailing_stop and trailing_stop > 0:
            ts_ck = self._check_tick_size(trailing_stop, "Trailing")
            if ts_ck:
                checks.append(ts_ck)

        # Quantity checks
        qs = self._check_step_size(quantity)
        if qs:
            checks.append(qs)
        qp = self._check_qty_precision(quantity)
        if qp:
            checks.append(qp)
        ls = self._check_lot_size(quantity)
        if ls:
            checks.append(ls)

        # Financial checks
        mn = self._check_min_notional(positional_value)
        if mn:
            checks.append(mn)
        mx = self._check_max_notional(positional_value)
        if mx:
            checks.append(mx)
        lv = self._check_leverage(leverage)
        if lv:
            checks.append(lv)
        mg = self._check_margin(positional_value, leverage, balance)
        if mg:
            checks.append(mg)

        # Liquidation
        liq_check, liq_price, liq_risk = self._check_liquidation_risk(
            entry_price, stop_loss, leverage, direction
        )
        checks.append(liq_check)

        # Fees
        maker_fee, taker_fee, total_fees, pos_val = self._calculate_fees(
            quantity, entry_price, stop_loss, take_profit_1
        )

        # Net RR
        gross_profit = abs(quantity * (take_profit_1 - entry_price))
        gross_loss = abs(quantity * (entry_price - stop_loss))
        slippage_cost = pos_val * self._slippage_rate * 2
        funding_est = pos_val * self._funding_rate_estimate
        net_profit = gross_profit - total_fees - slippage_cost - funding_est
        net_loss = gross_loss + total_fees + slippage_cost + funding_est
        net_rr = net_profit / net_loss if net_loss > 0 else 0.0

        fee_check = ValidationCheckItem(
            name="Fees", passed=True,
            expected=f"maker={maker_fee:.8f} taker={taker_fee:.8f}",
            found=f"total={total_fees:.8f}",
        )
        checks.append(fee_check)

        overall = all(c.passed for c in checks)
        hard_fail = ""
        if not overall and self._block_invalid:
            failed_checks = [c.name for c in checks if not c.passed]
            hard_fail = f"EXCHANGE_VALIDATION_FAILED: {', '.join(failed_checks)}"

        return ExecutionValidationResult(
            checks=checks,
            overall=overall,
            hard_fail_reason=hard_fail,
            tick_size=self._info.tick_size,
            step_size=self._info.step_size,
            liquidation_price=liq_price,
            liquidation_risk=liq_risk,
            maker_fee=maker_fee,
            taker_fee=taker_fee,
            funding_estimate=funding_est,
            slippage_cost=slippage_cost,
            net_rr=net_rr,
            net_profit=net_profit,
            net_loss=net_loss,
            total_fees=total_fees,
            position_value=pos_val,
            margin_required=pos_val / max(leverage, 0.01),
            margin_available=balance,
        )
