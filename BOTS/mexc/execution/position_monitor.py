import logging
from typing import Dict, List

from ..bot_config import BotConfig
from ..bot_types import Position
from ..exchange.connector import ExchangeConnector
from ..trading.position_manager import BotPositionManager

log = logging.getLogger(__name__)


class PositionMonitor:
    def __init__(self, config: BotConfig, exchange: ExchangeConnector, position_manager: BotPositionManager):
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
