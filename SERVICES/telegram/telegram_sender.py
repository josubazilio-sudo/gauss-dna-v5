import logging
import asyncio
import os
from pathlib import Path
from telegram import Bot
from dotenv import dotenv_values

log = logging.getLogger(__name__)

class TelegramSender:
    def __init__(self):
        # Usando pathlib para portabilidade
        base_dir = Path(__file__).resolve().parent.parent.parent
        env_path = base_dir / ".env"
        
        if not env_path.exists():
            log.error(f"Arquivo .env não encontrado em: {env_path}")
            raise FileNotFoundError(f"Arquivo .env não encontrado em: {env_path}")
            
        config = dotenv_values(env_path)
        token = config.get("TELEGRAM_BOT_TOKEN")
        self._chat_id = config.get("TELEGRAM_CHAT_ID")
        
        if not token or not self._chat_id:
            raise ValueError("TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID faltando no .env")
            
        self._bot = Bot(token=token)

    async def send(self, text: str):
        """
        Envia mensagem com Retry Exponencial:
        Tentativa 1 -> Falha -> Espera 2s -> Tentativa 2 -> Falha -> Espera 4s -> Tentativa 3 -> Falha -> Exception
        """
        max_retries = 3
        backoff = [0, 2, 4]  # Esperas em segundos

        for attempt in range(1, max_retries + 1):
            try:
                await self._bot.send_message(
                    chat_id=self._chat_id,
                    text=text,
                    parse_mode='Markdown'
                )
                return # Sucesso
            except Exception as e:
                log.warning(f"Tentativa {attempt} falhou ao enviar Telegram: {e}")
                if attempt == max_retries:
                    log.error("Todas as tentativas de envio falharam.")
                    raise
                
                wait = backoff[attempt]
                log.info(f"Aguardando {wait}s antes da próxima tentativa...")
                await asyncio.sleep(wait)
