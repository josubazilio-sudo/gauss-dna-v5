import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from ..bot_config import BotConfig
from ..bot_types import BotStatus, DailyStats, Order, OrderSide, OrderStatus, Position, SignalApproval
from .position_manager import BotPositionManager

log = logging.getLogger(__name__)


class CircuitBreaker:
    def __init__(self, max_consecutive_losses: int, cooldown_minutes: int):
        self._max_consecutive = max_consecutive_losses
        self._cooldown = cooldown_minutes
        self._consecutive_losses = 0
        self._active = False
        self._triggered_at: Optional[datetime] = None

    @property
    def active(self) -> bool:
        if self._active and self._triggered_at:
            elapsed = (datetime.now(timezone.utc) - self._triggered_at).total_seconds() / 60
            if elapsed >= self._cooldown:
                self.reset()
        return self._active

    def record_loss(self) -> None:
        self._consecutive_losses += 1
        if self._consecutive_losses >= self._max_consecutive:
            self._active = True
            self._triggered_at = datetime.now(timezone.utc)
            log.warning("CircuitBreaker: triggered after %d consecutive losses", self._consecutive_losses)

    def record_win(self) -> None:
        self._consecutive_losses = 0

    def reset(self) -> None:
        self._consecutive_losses = 0
        self._active = False
        self._triggered_at = None
        log.info("CircuitBreaker: reset")


class BotRiskManager:
    def __init__(self, config: BotConfig, position_manager: BotPositionManager):
        self._config = config
        self._pm = position_manager
        self._daily_stats: Dict[str, DailyStats] = {}
        self._circuit_breaker = CircuitBreaker(
            config.circuit_breaker_consecutive_losses,
            config.circuit_breaker_cooldown_minutes,
        )
        self._day_peak: float = 0.0
        self._day_start_balance: float = 0.0
        self._daily_positions_taken: int = 0

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        return self._circuit_breaker

    @property
    def daily_positions_taken(self) -> int:
        return self._daily_positions_taken

    def initialize_day(self, balance: float) -> None:
        self._day_start_balance = balance
        self._day_peak = balance
        self._daily_positions_taken = 0

    def can_open_position(self, balance: float, price: float, spread_pct: float) -> bool:
        if not self._config.enabled:
            return False
        if self._circuit_breaker.active:
            log.warning("BotRiskManager: circuit breaker active")
            return False
        if not self._pm.can_open_new():
            return False
        if self._daily_positions_taken >= self._config.daily_position_limit:
            log.warning("BotRiskManager: daily limit reached")
            return False
        if spread_pct > self._config.max_spread_pct:
            log.warning("BotRiskManager: spread %.4f exceeds max %.4f", spread_pct, self._config.max_spread_pct)
            return False
        dd_pct = self._current_daily_drawdown(balance)
        if dd_pct > self._config.max_daily_drawdown_pct:
            log.warning("BotRiskManager: daily drawdown %.4f exceeds limit", dd_pct)
            return False
        return True

    def calculate_position_size(
        self, balance: float, entry_price: float, stop_loss: float,
        quality_score: float = 0.0,
    ) -> float:
        base_pct = self._config.position_size_pct
        q = quality_score * 100.0 if quality_score <= 1.0 else quality_score
        if q >= 95:
            pct = base_pct * 3.0
        elif q >= 90:
            pct = base_pct * 2.5
        elif q >= 80:
            pct = base_pct * 2.0
        elif q >= 70:
            pct = base_pct * 1.5
        elif q >= 60:
            pct = base_pct * 1.2
        else:
            pct = base_pct
        risk_per_trade = balance * min(pct, 0.10)
        price_risk = abs(entry_price - stop_loss)
        if price_risk <= 0:
            return 0.0
        qty = risk_per_trade / price_risk
        max_qty = balance * self._config.max_daily_drawdown_pct / price_risk
        return min(qty, max_qty)

    def record_trade_result(self, pnl: float) -> None:
        if pnl > 0:
            self._circuit_breaker.record_win()
        else:
            self._circuit_breaker.record_loss()
        self._daily_positions_taken += 1
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today not in self._daily_stats:
            self._daily_stats[today] = DailyStats(date=today)
        stats = self._daily_stats[today]
        stats.total_trades += 1
        if pnl > 0:
            stats.winning_trades += 1
            stats.gross_profit += pnl
        else:
            stats.losing_trades += 1
            stats.gross_loss += abs(pnl)
        stats.net_pnl += pnl

    def update_peak(self, balance: float) -> None:
        if balance > self._day_peak:
            self._day_peak = balance

    def _current_daily_drawdown(self, balance: float) -> float:
        if self._day_peak <= 0:
            return 0.0
        return (self._day_peak - balance) / self._day_peak

    def get_daily_stats(self, date: str = "") -> Optional[DailyStats]:
        if not date:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self._daily_stats.get(date)

    def get_daily_report(self) -> str:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        stats = self._daily_stats.get(today)
        if not stats:
            return f"Daily Report {today}: no trades"
        return (
            f"Daily Report {today}: "
            f"Trades={stats.total_trades} "
            f"Wins={stats.winning_trades} "
            f"Losses={stats.losing_trades} "
            f"Net PnL={stats.net_pnl:.2f} "
            f"Drawdown={stats.max_drawdown:.4f}"
        )

    def reset_daily(self) -> None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self._daily_stats[today] = DailyStats(date=today)
        self._daily_positions_taken = 0
