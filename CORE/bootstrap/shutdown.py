import logging
from typing import Callable, List

log = logging.getLogger(__name__)


class Shutdown:
    def __init__(self, handlers: List[Callable[[], None]] | None = None):
        self._handlers = handlers or []

    def register(self, handler: Callable[[], None]) -> None:
        self._handlers.append(handler)

    def run(self) -> None:
        log.info("Finalizando QuantOS")
        for handler in reversed(self._handlers):
            try:
                handler()
            except Exception as e:
                log.error(f"Shutdown handler failed: {e}")
        log.info("Sistema encerrado")
