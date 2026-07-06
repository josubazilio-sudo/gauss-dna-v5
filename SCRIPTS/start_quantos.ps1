$env:PYTHONPATH = "C:\Users\josue\QuantOS"
python -c "
from BOTS.mexc.bot_engine import BotEngine
from BOTS.mexc.bot_config import BotConfig
from SERVICES.telegram.telegram_service import TelegramService
from CORE.events.event_bus import EventBus
import time

bus = EventBus()
config = BotConfig(dry_run=True, sandbox=True)
bot = BotEngine(config, bus)
telegram = TelegramService(bus)

bot.start()
while True:
    time.sleep(60)
"
