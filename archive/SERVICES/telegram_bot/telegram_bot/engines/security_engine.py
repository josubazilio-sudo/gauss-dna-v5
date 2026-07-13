import logging
from ..bot_config import TelegramConfig # Assume que criaremos essa config

log = logging.getLogger(__name__)

class SecurityEngine:
    def __init__(self, authorized_chat_id: str):
        self._authorized_chat_id = authorized_chat_id

    def is_authorized(self, chat_id: str) -> bool:
        return str(chat_id) == str(self._authorized_chat_id)

    def log_command(self, chat_id: str, command: str) -> None:
        log.info(f"TelegramCommand: User {chat_id} executed /{command}")
