import logging
from typing import Optional, Tuple

from ..bot_config import BotConfig
from ..bot_types import Balance, ConnectionStatus, Order, OrderSide, OrderType, TimeInForce
from CORE.execution.mode_manager import ExecutionModeManager
from .api_manager import APIManager
from .auth_manager import AuthenticationManager
from .websocket_manager import WebSocketManager

log = logging.getLogger(__name__)


class ExchangeConnector:
    def __init__(self, config: BotConfig):
        self._config = config
        self._auth = AuthenticationManager(config)
        self._api = APIManager(config, self._auth)
        self._ws = WebSocketManager(config)

    @property
    def auth(self) -> AuthenticationManager:
        return self._auth

    @property
    def api(self) -> APIManager:
        return self._api

    @property
    def ws(self) -> WebSocketManager:
        return self._ws

    @property
    def is_connected(self) -> bool:
        return self._api.status == ConnectionStatus.CONNECTED

    def connect(self, api_key: str, api_secret: str) -> bool:
        self._auth.authenticate(api_key, api_secret)
        api_ok = self._api.connect()
        ws_ok = self._ws.connect()
        if api_ok:
            log.info("ExchangeConnector: fully connected")
        return api_ok

    def disconnect(self) -> None:
        self._ws.disconnect()
        self._api.disconnect()
        log.info("ExchangeConnector: disconnected")

    def reconnect(self) -> bool:
        self.disconnect()
        return self.connect(self._auth.api_key, "")

    def get_balance(self) -> Balance:
        mode = ExecutionModeManager()
        if not mode.is_live():
            return Balance(total=10000.0, free=10000.0, used=0.0)
        return self._api.get_balance()

    def get_server_time(self) -> int:
        return self._api.get_server_time()

    def get_current_price(self, pair: str) -> float:
        mode = ExecutionModeManager()
        if mode.is_development():
            # DEVELOPMENT usa MockDataProvider para tudo — preco fixo evita
            # misturar dado sintetico com preco real da MEXC.
            prices = {"BTCUSDT": 65000.0, "ETHUSDT": 3500.0, "SOLUSDT": 145.0}
            return prices.get(pair, 100.0)
        try:
            price = self._api.get_ticker_price(pair)
            if price > 0:
                return price
        except Exception as e:
            log.warning("ExchangeConnector: falha ao buscar preco real de %s: %s", pair, e)
        prices = {"BTCUSDT": 65000.0, "ETHUSDT": 3500.0, "SOLUSDT": 145.0}
        return prices.get(pair, 100.0)

    def create_market_order(self, pair: str, side: OrderSide, quantity: float,
                            reduce_only: bool = False) -> Optional[Order]:
        return self._api.create_order(pair, side, OrderType.MARKET, quantity, reduce_only=reduce_only)

    def create_limit_order(self, pair: str, side: OrderSide, quantity: float, price: float,
                           tif: TimeInForce = TimeInForce.GTC, reduce_only: bool = False) -> Optional[Order]:
        return self._api.create_order(pair, side, OrderType.LIMIT, quantity, price=price,
                                       time_in_force=tif, reduce_only=reduce_only)

    def create_stop_order(self, pair: str, side: OrderSide, quantity: float, stop_price: float,
                          reduce_only: bool = True) -> Optional[Order]:
        return self._api.create_order(pair, side, OrderType.STOP, quantity, stop_price=stop_price,
                                       reduce_only=reduce_only)

    def create_stop_limit_order(self, pair: str, side: OrderSide, quantity: float,
                                 stop_price: float, price: float, reduce_only: bool = True) -> Optional[Order]:
        return self._api.create_order(pair, side, OrderType.STOP_LIMIT, quantity,
                                       price=price, stop_price=stop_price, reduce_only=reduce_only)

    def cancel_order(self, pair: str, order_id: str) -> bool:
        return self._api.cancel_order(pair, order_id)

    def get_order_status(self, pair: str, order_id: str) -> Optional[dict]:
        return self._api.get_order_status(pair, order_id)

    def get_open_orders(self, pair: str) -> list:
        return self._api.get_open_orders(pair)
