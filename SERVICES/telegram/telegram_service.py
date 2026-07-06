import logging
import asyncio
from CORE.events.event_bus import EventBus
from .telegram_sender import TelegramSender
from .telegram_formatter import TelegramFormatter

log = logging.getLogger(__name__)

class TelegramService:
    def __init__(self, event_bus: EventBus):
        self._bus = event_bus
        self._sender = TelegramSender()
        self._formatter = TelegramFormatter()
        
        # Subscrição a eventos do QuantOS
        self._bus.subscribe("signal.generated", self._on_signal)
        self._bus.subscribe("trade.opened", self._on_trade_open)
        self._bus.subscribe("trade.closed", self._on_trade_closed)

    def _on_signal(self, event):
        msg = self._formatter.format_signal(event.data)
        asyncio.run(self._sender.send(msg))

    def _on_trade_open(self, event):
        msg = self._formatter.format_op_iniciada(event.data)
        asyncio.run(self._sender.send(msg))

    def _on_trade_closed(self, event):
        msg = self._formatter.format_op_finalizada(event.data)
        asyncio.run(self._sender.send(msg))
