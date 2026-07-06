import json
import logging
import threading
import time
from typing import Callable, Dict, List, Optional

from ..bot_config import BotConfig
from ..bot_types import ConnectionStatus

log = logging.getLogger(__name__)


class WebSocketManager:
    def __init__(self, config: BotConfig):
        self._config = config
        self._url = config.mexc_websocket_url
        self._status = ConnectionStatus.DISCONNECTED
        self._subscriptions: Dict[str, List[Callable]] = {}
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._last_ping = 0.0

    @property
    def status(self) -> ConnectionStatus:
        return self._status

    def connect(self) -> bool:
        self._status = ConnectionStatus.CONNECTED
        self._running = True
        log.info("WebSocketManager: connected to %s", self._url)
        return True

    def disconnect(self) -> None:
        self._running = False
        self._status = ConnectionStatus.DISCONNECTED
        log.info("WebSocketManager: disconnected")

    def subscribe(self, channel: str, callback: Callable) -> None:
        if channel not in self._subscriptions:
            self._subscriptions[channel] = []
        self._subscriptions[channel].append(callback)
        log.info("WebSocketManager: subscribed to %s", channel)

    def unsubscribe(self, channel: str, callback: Callable) -> None:
        if channel in self._subscriptions:
            self._subscriptions[channel].remove(callback)
            log.info("WebSocketManager: unsubscribed from %s", channel)

    def subscribe_ticker(self, pair: str, callback: Callable) -> None:
        channel = f"ticker.{pair.lower()}"
        self.subscribe(channel, callback)

    def subscribe_kline(self, pair: str, interval: str, callback: Callable) -> None:
        channel = f"kline.{pair.lower()}.{interval}"
        self.subscribe(channel, callback)

    def subscribe_depth(self, pair: str, callback: Callable) -> None:
        channel = f"depth.{pair.lower()}"
        self.subscribe(channel, callback)

    def subscribe_account(self, callback: Callable) -> None:
        self.subscribe("account", callback)

    def subscribe_orders(self, callback: Callable) -> None:
        self.subscribe("orders", callback)

    def on_message(self, channel: str, data: dict) -> None:
        callbacks = self._subscriptions.get(channel, [])
        for cb in callbacks:
            try:
                cb(data)
            except Exception:
                log.exception("WebSocketManager: callback failed for %s", channel)
