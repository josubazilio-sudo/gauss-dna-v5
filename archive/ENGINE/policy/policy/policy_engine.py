import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from CORE.events.event_bus import EventBus
from CORE.events.events import Event, EventTypes
from ENGINE.council.council_types import CouncilVerdict
from ENGINE.meta.meta_types import MetaVerdict
from ENGINE.policy.policy_types import PolicyVerdict
from ENGINE.policy.policy_config import (
    ENABLE_MAX_POSITIONS, MAX_POSITIONS,
    ENABLE_MAX_DAILY_OPERATIONS, MAX_DAILY_OPERATIONS,
    ENABLE_MAX_DAILY_RISK, MAX_DAILY_RISK,
    ENABLE_MAX_DAILY_DRAWDOWN, MAX_DAILY_DRAWDOWN,
    ENABLE_MAX_WEEKLY_DRAWDOWN, MAX_WEEKLY_DRAWDOWN,
    ENABLE_MAX_MONTHLY_DRAWDOWN, MAX_MONTHLY_DRAWDOWN,
    ENABLE_MAX_EXPOSURE_PER_ASSET, MAX_EXPOSURE_PER_ASSET,
    ENABLE_MAX_EXPOSURE_PER_SECTOR, MAX_EXPOSURE_PER_SECTOR,
    ENABLE_MAX_EXPOSURE_PER_DIRECTION, MAX_EXPOSURE_PER_DIRECTION,
    ENABLE_MAX_CORRELATION, MAX_CORRELATION,
    ENABLE_MAX_LEVERAGE, MAX_LEVERAGE,
    ENABLE_TRADING_HOURS, TRADING_HOURS_START, TRADING_HOURS_END,
    ENABLE_CIRCUIT_BREAKER,
    ENABLE_HIGH_VOLATILITY_BLOCK,
    ENABLE_MACRO_EVENT_BLOCK,
    COMPLIANCE_PERFECT, COMPLIANCE_PENALTY_PER_RULE, COMPLIANCE_MIN,
)
from ENGINE.world.world_types import WorldModel

log = logging.getLogger(__name__)


class PolicyEngine:

    def __init__(self, event_bus: Optional[EventBus] = None):
        self._event_bus = event_bus

    def evaluate(
        self,
        meta_verdict: Optional[MetaVerdict],
        world_model: Optional[WorldModel],
        council_verdict: Optional[CouncilVerdict],
        context: Optional[Dict[str, Any]],
    ) -> PolicyVerdict:
        violated: List[str] = []
        warnings: List[str] = []
        recommendations: List[str] = []

        ctx = context or {}
        open_positions = ctx.get("open_positions") or []
        daily_risk_used = ctx.get("daily_risk_used", 0.0)
        daily_drawdown = ctx.get("daily_drawdown", 0.0)
        weekly_drawdown = ctx.get("weekly_drawdown", 0.0)
        monthly_drawdown = ctx.get("monthly_drawdown", 0.0)
        exposure_by_asset = ctx.get("exposure_by_asset") or {}
        exposure_by_sector = ctx.get("exposure_by_sector") or {}
        exposure_long = ctx.get("exposure_long", 0.0)
        exposure_short = ctx.get("exposure_short", 0.0)
        avg_correlation = ctx.get("avg_correlation", 0.0)
        current_leverage = ctx.get("current_leverage", 0.0)
        trading_hour = ctx.get("trading_hour", datetime.now(timezone.utc).hour)
        circuit_breaker = ctx.get("circuit_breaker_active", False)
        high_volatility = ctx.get("high_volatility", False)
        macro_event = ctx.get("macro_event_block", False)
        daily_ops = ctx.get("daily_operations", 0)

        n_positions = len(open_positions)

        # -- Regras --
        self._check_max_positions(n_positions, violated, warnings, recommendations)
        self._check_daily_operations(daily_ops, violated, warnings, recommendations)
        self._check_max_daily_risk(daily_risk_used, violated, warnings, recommendations)
        self._check_daily_drawdown(daily_drawdown, violated, warnings, recommendations)
        self._check_weekly_drawdown(weekly_drawdown, violated, warnings, recommendations)
        self._check_monthly_drawdown(monthly_drawdown, violated, warnings, recommendations)
        self._check_exposure_per_asset(exposure_by_asset, violated, warnings, recommendations)
        self._check_exposure_per_sector(exposure_by_sector, violated, warnings, recommendations)
        self._check_exposure_per_direction(exposure_long, exposure_short, violated, warnings, recommendations)
        self._check_correlation(avg_correlation, violated, warnings, recommendations)
        self._check_leverage(current_leverage, violated, warnings, recommendations)
        self._check_trading_hours(trading_hour, violated, warnings, recommendations)
        self._check_circuit_breaker(circuit_breaker, violated, warnings, recommendations)
        self._check_high_volatility(high_volatility, violated, warnings, recommendations)
        self._check_macro_event(macro_event, violated, warnings, recommendations)

        allowed = len(violated) == 0
        decision = "ALLOWED" if allowed else "BLOCKED"
        compliance = self._compliance_score(len(violated))

        verdict = PolicyVerdict(
            allowed=allowed,
            decision=decision,
            compliance_score=round(compliance, 4),
            violated_rules=violated,
            warnings=warnings,
            recommendations=recommendations,
            policy_hash="",
        )

        final = PolicyVerdict(
            allowed=verdict.allowed,
            decision=verdict.decision,
            compliance_score=verdict.compliance_score,
            violated_rules=verdict.violated_rules,
            warnings=verdict.warnings,
            recommendations=verdict.recommendations,
            policy_hash=PolicyVerdict.compute_hash(verdict),
            created_at=verdict.created_at,
        )

        self._publish(final)
        return final

    def _check_max_positions(
        self, n: int,
        violated: List[str], warnings: List[str], recommendations: List[str],
    ) -> None:
        if not ENABLE_MAX_POSITIONS:
            return
        if n >= MAX_POSITIONS:
            violated.append("Limite de posicoes simultaneas atingido")
            recommendations.append("Encerrar posicao antes de abrir nova")
        elif n >= MAX_POSITIONS - 1:
            warnings.append("Proximo do limite de posicoes")

    def _check_daily_operations(
        self, ops: int,
        violated: List[str], warnings: List[str], recommendations: List[str],
    ) -> None:
        if not ENABLE_MAX_DAILY_OPERATIONS:
            return
        if ops >= MAX_DAILY_OPERATIONS:
            violated.append("Limite diario de operacoes atingido")
            recommendations.append("Limite diario atingido")
        elif ops >= MAX_DAILY_OPERATIONS - 2:
            warnings.append("Proximo do limite diario de operacoes")

    def _check_max_daily_risk(
        self, risk: float,
        violated: List[str], warnings: List[str], recommendations: List[str],
    ) -> None:
        if not ENABLE_MAX_DAILY_RISK:
            return
        if risk >= MAX_DAILY_RISK:
            violated.append("Risco diario maximo excedido")
            recommendations.append("Reduzir exposicao")
        elif risk >= MAX_DAILY_RISK * 0.8:
            warnings.append("Risco diario proximo do limite")

    def _check_daily_drawdown(
        self, dd: float,
        violated: List[str], warnings: List[str], recommendations: List[str],
    ) -> None:
        if not ENABLE_MAX_DAILY_DRAWDOWN:
            return
        if dd >= MAX_DAILY_DRAWDOWN:
            violated.append("Drawdown diario maximo excedido")
            recommendations.append("Aguardar reducao do drawdown")
        elif dd >= MAX_DAILY_DRAWDOWN * 0.8:
            warnings.append("Drawdown diario proximo do limite")

    def _check_weekly_drawdown(
        self, dd: float,
        violated: List[str], warnings: List[str], recommendations: List[str],
    ) -> None:
        if not ENABLE_MAX_WEEKLY_DRAWDOWN:
            return
        if dd >= MAX_WEEKLY_DRAWDOWN:
            violated.append("Drawdown semanal maximo excedido")
            recommendations.append("Aguardar reducao do drawdown semanal")
        elif dd >= MAX_WEEKLY_DRAWDOWN * 0.8:
            warnings.append("Drawdown semanal proximo do limite")

    def _check_monthly_drawdown(
        self, dd: float,
        violated: List[str], warnings: List[str], recommendations: List[str],
    ) -> None:
        if not ENABLE_MAX_MONTHLY_DRAWDOWN:
            return
        if dd >= MAX_MONTHLY_DRAWDOWN:
            violated.append("Drawdown mensal maximo excedido")
            recommendations.append("Aguardar reducao do drawdown mensal")
        elif dd >= MAX_MONTHLY_DRAWDOWN * 0.8:
            warnings.append("Drawdown mensal proximo do limite")

    def _check_exposure_per_asset(
        self, exposure: Dict[str, float],
        violated: List[str], warnings: List[str], recommendations: List[str],
    ) -> None:
        if not ENABLE_MAX_EXPOSURE_PER_ASSET:
            return
        for symbol, exp in exposure.items():
            if exp > MAX_EXPOSURE_PER_ASSET:
                violated.append(f"Exposicao excessiva ao ativo {symbol}")
                if recommendations and "Reduzir exposicao" not in recommendations:
                    recommendations.append("Reduzir exposicao")

    def _check_exposure_per_sector(
        self, exposure: Dict[str, float],
        violated: List[str], warnings: List[str], recommendations: List[str],
    ) -> None:
        if not ENABLE_MAX_EXPOSURE_PER_SECTOR:
            return
        for sector, exp in exposure.items():
            if exp > MAX_EXPOSURE_PER_SECTOR:
                violated.append(f"Exposicao excessiva ao setor {sector}")
                if recommendations and "Reduzir exposicao" not in recommendations:
                    recommendations.append("Reduzir exposicao")

    def _check_exposure_per_direction(
        self, long: float, short: float,
        violated: List[str], warnings: List[str], recommendations: List[str],
    ) -> None:
        if not ENABLE_MAX_EXPOSURE_PER_DIRECTION:
            return
        if long > MAX_EXPOSURE_PER_DIRECTION:
            violated.append("Exposicao excessiva em LONG")
            recommendations.append("Reduzir exposicao LONG")
        if short > MAX_EXPOSURE_PER_DIRECTION:
            violated.append("Exposicao excessiva em SHORT")
            recommendations.append("Reduzir exposicao SHORT")

    def _check_correlation(
        self, corr: float,
        violated: List[str], warnings: List[str], recommendations: List[str],
    ) -> None:
        if not ENABLE_MAX_CORRELATION:
            return
        if corr > MAX_CORRELATION:
            violated.append("Correlacao elevada entre posicoes")
            recommendations.append("Correlacao elevada entre posicoes")
        elif corr > MAX_CORRELATION * 0.85:
            warnings.append("Correlacao entre posicoes proxima do limite")

    def _check_leverage(
        self, lev: float,
        violated: List[str], warnings: List[str], recommendations: List[str],
    ) -> None:
        if not ENABLE_MAX_LEVERAGE:
            return
        if lev > MAX_LEVERAGE:
            violated.append("Limite de alavancagem excedido")
            recommendations.append("Reduzir alavancagem")
        elif lev > MAX_LEVERAGE * 0.85:
            warnings.append("Alavancagem proxima do limite")

    def _check_trading_hours(
        self, hour: int,
        violated: List[str], warnings: List[str], recommendations: List[str],
    ) -> None:
        if not ENABLE_TRADING_HOURS:
            return
        if hour < TRADING_HOURS_START or hour >= TRADING_HOURS_END:
            violated.append("Horario de operacao bloqueado")
            recommendations.append("Aguardar horario permitido para operar")

    def _check_circuit_breaker(
        self, active: bool,
        violated: List[str], warnings: List[str], recommendations: List[str],
    ) -> None:
        if not ENABLE_CIRCUIT_BREAKER:
            return
        if active:
            violated.append("Circuit Breaker ativo")
            recommendations.append("Circuit Breaker ativo")

    def _check_high_volatility(
        self, active: bool,
        violated: List[str], warnings: List[str], recommendations: List[str],
    ) -> None:
        if not ENABLE_HIGH_VOLATILITY_BLOCK:
            return
        if active:
            violated.append("Alta volatilidade extrema detectada")
            recommendations.append("Aguardar normalizacao da volatilidade")

    def _check_macro_event(
        self, active: bool,
        violated: List[str], warnings: List[str], recommendations: List[str],
    ) -> None:
        if not ENABLE_MACRO_EVENT_BLOCK:
            return
        if active:
            violated.append("Evento macro critico em andamento")
            recommendations.append("Aguardar evento macro")

    @staticmethod
    def _compliance_score(n_violations: int) -> float:
        score = COMPLIANCE_PERFECT - n_violations * COMPLIANCE_PENALTY_PER_RULE
        return max(COMPLIANCE_MIN, score)

    def _publish(self, verdict: PolicyVerdict) -> None:
        if self._event_bus is None:
            return
        try:
            event_type = (
                EventTypes.POLICY_APPROVED if verdict.allowed
                else EventTypes.POLICY_BLOCKED
            )
            self._event_bus.publish(Event(
                event_type,
                {"verdict": verdict.to_dict()},
            ))
        except Exception as e:
            log.error("Failed to publish policy event: %s", e)
