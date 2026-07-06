import logging
from typing import Any, Dict, List

from ..bot_config import BotConfig
from ..bot_types import OrderSide, Position
from ..exchange.connector import ExchangeConnector
from ..trading.position_manager import BotPositionManager

log = logging.getLogger(__name__)


class PositionMonitor:
    def __init__(self, config: BotConfig, exchange: ExchangeConnector,
                 position_manager: BotPositionManager):
        self._config = config
        self._exchange = exchange
        self._pm = position_manager

    def monitor_all(self) -> List[Position]:
        positions = self._pm.all_positions()
        if not positions:
            return []

        prices: Dict[str, float] = {}
        for pos in positions:
            if pos.quantity > 0 and pos.pair not in prices:
                try:
                    prices[pos.pair] = self._exchange.get_current_price(pos.pair)
                except Exception:
                    pass

        self._pm.update_prices(prices)
        return self._pm.all_positions()

    def continuous_revalidation(self, position: Position, current_price: float,
                                structure_broken: bool, regime_changed: bool,
                                bos_contrario: bool, choch_contrario: bool) -> str:
        if position.quantity <= 0:
            return "closed"

        reasons = []

        if structure_broken:
            reasons.append("Estrutura quebrada")
        if regime_changed:
            reasons.append("Mudança de regime")
        if bos_contrario:
            reasons.append("BOS contrário detectado")
        if choch_contrario:
            reasons.append("CHOCH contrário detectado")

        if position.side == OrderSide.BUY:
            trend_up = current_price >= position.entry_price
            if not trend_up:
                reasons.append("Perda de tendência (abaixo da entrada)")
        else:
            trend_down = current_price <= position.entry_price
            if not trend_down:
                reasons.append("Perda de tendência (acima da entrada)")

        if reasons:
            log.warning(
                "PositionMonitor v4.0: Revalidação falhou para %s %s — %s",
                position.pair, position.side.value, "; ".join(reasons),
            )
            return "exit"

        return "hold"
