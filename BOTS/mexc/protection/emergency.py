import logging
from datetime import datetime, timezone

from ..bot_config import BotConfig
from ..bot_types import OrderSide
from ..trading.execution_engine import ExecutionEngine
from ..trading.position_manager import BotPositionManager

log = logging.getLogger(__name__)


class EmergencyProtection:
    def __init__(self, config: BotConfig, position_manager: BotPositionManager, execution_engine: ExecutionEngine):
        self._config = config
        self._pm = position_manager
        self._ee = execution_engine
        self._triggered = False

    @property
    def triggered(self) -> bool:
        return self._triggered

    def check_protections(self, total_balance: float, current_spread: float = 0.0) -> bool:
        if self._triggered:
            return True

        # Check de Liquidez/Spread Crítico
        if current_spread > self._config.max_spread_pct * 3:
            log.critical(f"EmergencyProtection: SPREAD CRÍTICO {current_spread:.4f} > 3x LIMITE. SHUTDOWN!")
            self.trigger_emergency_close()
            return True

        positions = self._pm.all_positions()
        if not positions:
            return False

        # Calculate absolute drawdown from unrealized PnL
        unrealized_pnl = sum(p.unrealized_pnl for p in positions)
        if total_balance > 0:
            dd_pct = abs(unrealized_pnl) / total_balance
            if dd_pct >= self._config.emergency_stop_loss_pct:
                log.critical("EmergencyProtection: DRAWDOWN %.2f%% EXCEEDS LIMIT %.2f%%. TRIGGERING EMERGENCY SHUTDOWN!",
                             dd_pct * 100, self._config.emergency_stop_loss_pct * 100)
                self.trigger_emergency_close()
                return True

        # Check for individual positions moving way beyond standard SL (circuit-breaker scenario)
        for pos in positions:
            if pos.quantity > 0:
                pnl_pct = pos.pnl_percent()
                if pnl_pct <= -self._config.emergency_stop_loss_pct * 100:
                    log.critical("EmergencyProtection: Position %s drawdown %.2f%% exceeds threshold. Liquidating immediately!",
                                 pos.pair, pnl_pct)
                    self._ee.close_position_market(pos.id)

        return False

    def trigger_emergency_close(self) -> None:
        log.warning("EmergencyProtection: closing all positions and cancelling all orders!")
        self._triggered = True
        closed = self._ee.close_all_positions()
        log.warning("EmergencyProtection: %d positions closed in emergency shutdown", closed)

    def reset(self) -> None:
        self._triggered = False
        log.info("EmergencyProtection: reset")
