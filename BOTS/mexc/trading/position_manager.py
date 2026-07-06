import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from ..bot_config import BotConfig
from ..bot_types import OrderSide, Position
from ..exchange.connector import ExchangeConnector

log = logging.getLogger(__name__)


class BotPositionManager:
    def __init__(self, config: BotConfig, exchange: ExchangeConnector):
        self._config = config
        self._exchange = exchange
        self._positions: Dict[str, Position] = {}

    def all_positions(self) -> List[Position]:
        return list(self._positions.values())

    def get_position(self, position_id: str) -> Optional[Position]:
        return self._positions.get(position_id)

    def get_position_by_pair(self, pair: str) -> Optional[Position]:
        for pos in self._positions.values():
            if pos.pair == pair:
                return pos
        return None

    def get_open_count(self) -> int:
        return len([p for p in self._positions.values() if p.quantity > 0])

    def can_open_new(self) -> bool:
        if self.get_open_count() >= self._config.max_positions:
            return False
        return True

    def open_position(self, pair: str, side: OrderSide, quantity: float, entry_price: float,
                      stop_loss: float, take_profit_1: float, take_profit_2: float,
                      atr_at_entry: float = 0.0, setup: str = "", regime: str = "",
                      signal_id: str = "", leverage: int = 1) -> Position:
        pos = Position(
            id=f"pos_{uuid.uuid4().hex[:12]}",
            pair=pair,
            side=side,
            quantity=quantity,
            entry_price=entry_price,
            current_price=entry_price,
            stop_loss=stop_loss,
            take_profit_1=take_profit_1,
            take_profit_2=take_profit_2,
            atr_at_entry=atr_at_entry,
            setup=setup,
            regime=regime,
            signal_id=signal_id,
            leverage=leverage,
        )
        self._positions[pos.id] = pos
        log.info("BotPositionManager: opened %s %s %.4f @ %.2f [%s]", side.value, pair, quantity, entry_price, setup)
        return pos

    def update_position(self, position_id: str, current_price: float) -> None:
        pos = self._positions.get(position_id)
        if not pos:
            return
        pos.current_price = current_price
        pos.updated_at = datetime.now(timezone.utc)
        diff = current_price - pos.entry_price
        if pos.side == OrderSide.SELL:
            diff = -diff
        pos.unrealized_pnl = diff * pos.quantity

    def update_prices(self, price_map: Dict[str, float]) -> None:
        for pos in self._positions.values():
            price = price_map.get(pos.pair)
            if price:
                self.update_position(pos.id, price)

    def close_position(self, position_id: str, exit_price: float) -> Optional[Position]:
        pos = self._positions.get(position_id)
        if not pos:
            return None
        diff = exit_price - pos.entry_price
        if pos.side == OrderSide.SELL:
            diff = -diff
        pos.realized_pnl = diff * pos.quantity
        pos.current_price = exit_price
        pos.quantity = 0.0
        pos.updated_at = datetime.now(timezone.utc)
        log.info("BotPositionManager: closed %s %s at %.2f (pnl: %.2f)", pos.side.value, pos.pair, exit_price, pos.realized_pnl)
        return pos

    def close_all(self, exit_price_map: Dict[str, float]) -> int:
        closed = 0
        for pos in list(self._positions.values()):
            if pos.quantity > 0:
                price = exit_price_map.get(pos.pair, pos.current_price)
                self.close_position(pos.id, price)
                closed += 1
        return closed

    def sync_positions(self) -> None:
        pass

    def create_dummy(self, signal) -> Position:
        pos = Position(
            id=f"dummy_{signal.signal_id}",
            pair=signal.pair,
            side=signal.order_side,
            quantity=1.0,
            entry_price=signal.entry_price,
            current_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            take_profit_1=signal.take_profit_1,
            take_profit_2=signal.take_profit_2,
            atr_at_entry=signal.atr,
            setup=signal.setup,
            regime=signal.regime,
            signal_id=signal.signal_id,
        )
        return pos

    def reset(self) -> None:
        self._positions.clear()
