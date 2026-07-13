import logging
import asyncio
from telegram import Bot
from dotenv import dotenv_values
from .telegram_formatter import TelegramFormatter

log = logging.getLogger(__name__)

class TelegramSender:
    def __init__(self):
        config = dotenv_values("TELEGRAM/.env")
        self._bot = Bot(token=config["TELEGRAM_BOT_TOKEN"])
        self._chat_id = config["TELEGRAM_CHAT_ID"]

    async def send(self, message: str):
        try:
            await self._bot.send_message(chat_id=self._chat_id, text=message, parse_mode='Markdown')
        except Exception as e:
            log.error(f"Erro ao enviar Telegram: {e}")
