import logging
from telegram.ext import ApplicationBuilder, CommandHandler
from .engines.notification_engine import NotificationEngine
from .engines.security_engine import SecurityEngine
from .engines.command_engine import CommandEngine

# ... (dentro do TelegramControlCenter) ...
    def __init__(self, token: str, chat_id: str, bot_engine: Any):
        self._app = ApplicationBuilder().token(token).build()
        self._security = SecurityEngine(chat_id)
        self._commands = CommandEngine(bot_engine)
        
        # Registrar comandos
        commands = ["status", "saldo", "performance"]
        for cmd in commands:
            self._app.add_handler(CommandHandler(cmd, self._generic_handler))

    async def _generic_handler(self, update, context):
        if not self._security.is_authorized(update.effective_chat.id): return
        cmd = update.message.text.lstrip("/")
        self._security.log_command(update.effective_chat.id, cmd)
        response = self._commands.execute(cmd)
        await update.message.reply_text(response)


    def run(self):
        log.info("TelegramControlCenter: Iniciado.")
        self._app.run_polling()
