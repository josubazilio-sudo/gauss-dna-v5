import json
import logging
import time
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

from ..bot_config import BotConfig
from ..bot_types import Balance, ConnectionStatus, Order, OrderSide, OrderStatus, OrderType, TimeInForce
from .auth_manager import AuthenticationManager

log = logging.getLogger(__name__)


class APIError(Exception):
    pass


class APIManager:
    def __init__(self, config: BotConfig, auth: AuthenticationManager):
        self._config = config
        self._auth = auth
        self._base_url = config.mexc_rest_url
        self._status = ConnectionStatus.DISCONNECTED
        self._last_request_ms = 0.0

    @property
    def status(self) -> ConnectionStatus:
        return self._status

    @property
    def last_latency_ms(self) -> float:
        return self._last_request_ms

    def connect(self) -> bool:
        try:
            self._request("GET", "/api/v3/ping")
            self._status = ConnectionStatus.CONNECTED
            log.info("APIManager: connected to MEXC REST API")
            return True
        except Exception as e:
            self._status = ConnectionStatus.DISCONNECTED
            log.error("APIManager: connection failed: %s", e)
            return False

    def disconnect(self) -> None:
        self._status = ConnectionStatus.DISCONNECTED
        log.info("APIManager: disconnected")

    def get_server_time(self) -> int:
        data = self._request("GET", "/api/v3/time")
        return int(data.get("serverTime", 0))

    def get_exchange_info(self) -> dict:
        return self._request("GET", "/api/v3/exchangeInfo")

    def get_balance(self) -> Balance:
        data = self._auth_request("GET", "/api/v3/account")
        bal = Balance()
        for asset in data.get("balances", []):
            if asset["asset"] == "USDT":
                bal.total = float(asset["free"]) + float(asset["locked"])
                bal.free = float(asset["free"])
                bal.used = float(asset["locked"])
        return bal

    def get_position_info(self) -> List[dict]:
        try:
            return self._auth_request("GET", "/api/v3/openOrders")
        except APIError:
            return []

    def create_order(
        self,
        pair: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: float,
        price: float = 0.0,
        stop_price: float = 0.0,
        time_in_force: TimeInForce = TimeInForce.GTC,
        reduce_only: bool = False,
    ) -> Optional[Order]:
        params = {
            "symbol": pair.replace("USDT", "USDT"),
            "side": side.value.upper(),
            "type": order_type.value.upper(),
            "quantity": self._format_quantity(quantity),
            "timestamp": self._auth.get_timestamp(),
        }
        if order_type == OrderType.LIMIT:
            params["price"] = self._format_price(price)
            params["timeInForce"] = time_in_force.value.upper()
        if order_type in (OrderType.STOP, OrderType.STOP_LIMIT):
            params["stopPrice"] = self._format_price(stop_price)
            if order_type == OrderType.STOP_LIMIT:
                params["price"] = self._format_price(price)
        if reduce_only:
            params["reduceOnly"] = "true"

        try:
            data = self._auth_request("POST", "/api/v3/order", params)
            order = Order(
                id=data.get("clientOrderId", ""),
                exchange_id=data.get("orderId", ""),
                pair=pair,
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price,
                stop_price=stop_price,
                status=OrderStatus.OPEN,
                time_in_force=time_in_force,
                reduce_only=reduce_only,
            )
            log.info("APIManager: order created %s %s %s %s", side.value, quantity, pair, order_type.value)
            return order
        except APIError as e:
            log.error("APIManager: order failed: %s", e)
            return None

    def cancel_order(self, pair: str, order_id: str) -> bool:
        params = {"symbol": pair.replace("USDT", "USDT"), "orderId": order_id, "timestamp": self._auth.get_timestamp()}
        try:
            self._auth_request("DELETE", "/api/v3/order", params)
            log.info("APIManager: cancelled order %s", order_id)
            return True
        except APIError as e:
            log.error("APIManager: cancel order %s failed: %s", order_id, e)
            return False

    def get_order_status(self, pair: str, order_id: str) -> Optional[dict]:
        params = {"symbol": pair.replace("USDT", "USDT"), "orderId": order_id, "timestamp": self._auth.get_timestamp()}
        try:
            return self._auth_request("GET", "/api/v3/order", params)
        except APIError:
            return None

    def get_open_orders(self, pair: str) -> List[dict]:
        params = {"symbol": pair.replace("USDT", "USDT"), "timestamp": self._auth.get_timestamp()}
        try:
            return self._auth_request("GET", "/api/v3/openOrders", params)
        except APIError:
            return []

    def get_ticker_price(self, pair: str) -> float:
        data = self._request("GET", f"/api/v3/ticker/price", {"symbol": pair.replace("USDT", "USDT")})
        return float(data.get("price", 0))

    def get_ticker_book(self, pair: str) -> Tuple[float, float, float]:
        data = self._request("GET", f"/api/v3/ticker/bookTicker", {"symbol": pair.replace("USDT", "USDT")})
        return (float(data.get("bidPrice", 0)), float(data.get("askPrice", 0)), float(data.get("bidQty", 0)))

    def _request(self, method: str, path: str, params: dict = None) -> Any:
        start = time.time()
        url = f"{self._base_url}{path}"
        if params:
            url += f"?{urlencode(params)}"
        req = urllib.request.Request(url, method=method)
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                self._last_request_ms = (time.time() - start) * 1000
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            raise APIError(f"HTTP {e.code}: {e.read().decode()}")
        except Exception as e:
            raise APIError(str(e))

    def _auth_request(self, method: str, path: str, params: dict = None) -> Any:
        params = params or {}
        req_params = {"timestamp": self._auth.get_timestamp(), **params}
        signed = self._auth.sign_request(req_params)
        url = f"{self._base_url}{path}"
        data = urllib.parse.urlencode(signed).encode()
        req = urllib.request.Request(url, data=data if method in ("POST", "DELETE") else None, method=method)
        for k, v in self._auth.generate_headers().items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            raise APIError(f"HTTP {e.code}: {e.read().decode()}")
        except Exception as e:
            raise APIError(str(e))

    def _format_quantity(self, qty: float) -> str:
        return f"{qty:.8f}".rstrip("0").rstrip(".")

    def _format_price(self, price: float) -> str:
        return f"{price:.8f}".rstrip("0").rstrip(".")
