import logging

from ..config.settings import Settings
from ..events.event_bus import EventBus
from ..errors.handlers import setup_global_handlers

log = logging.getLogger(__name__)


class Startup:
    def __init__(self):
        self._settings = Settings()
        self._event_bus = EventBus()

    def run(self) -> None:
        setup_global_handlers()
        log.info(f"Iniciando {self._settings.constants.PROJECT_NAME}")
        log.info(f"Ambiente: {self._settings.env.type.value}")
        log.info("Núcleo inicializado com sucesso")
