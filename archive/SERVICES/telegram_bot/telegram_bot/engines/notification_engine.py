import logging
from typing import Any
from ....CORE.events.event_bus import EventBus
from ....CORE.events.events import Event

log = logging.getLogger(__name__)

class NotificationEngine:
    def __init__(self, bot_instance: Any, chat_id: str):
        self._bot = bot_instance
        self._chat_id = chat_id

    def send_message(self, message: str) -> None:
        # Método para envio síncrono (wrapper para o bot do telegram)
        try:
            self._bot.bot.send_message(chat_id=self._chat_id, text=message)
        except Exception as e:
            log.error(f"Erro ao enviar Telegram: {e}")

    def _on_event(self, event: Event) -> None:
        message = f"📢 *{event.type.upper()}*\n{event.data.get('message', '')}"
        self.send_message(message)
