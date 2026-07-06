import logging
from telegram import Bot
from dotenv import dotenv_values
import asyncio

log = logging.getLogger(__name__)

class TelegramSender:
    def __init__(self):
        config = dotenv_values("C:/Users/josue/QuantOS/TELEGRAM/.env")
        self._bot = Bot(token=config["TELEGRAM_BOT_TOKEN"])
        self._chat_id = config["TELEGRAM_CHAT_ID"]

    async def send(self, text: str):
        try:
            await self._bot.send_message(
                chat_id=self._chat_id,
                text=text,
                parse_mode='Markdown'
            )
        except Exception as e:
            log.error(f"Erro ao enviar sinal via Telegram: {e}")
            raise
