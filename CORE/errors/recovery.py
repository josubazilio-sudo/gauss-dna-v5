"""
Procedimentos de recuperação de erros.

Tenta restaurar o sistema a um estado seguro após falhas.
"""

import logging
from ..events.event_bus import EventBus
from ..events.events import Event, EventTypes

log = logging.getLogger(__name__)


class Recovery:
    """Sistema de recuperação após falhas.

    Publica eventos de tentativa de recuperação e rollback
    para que outros módulos possam reagir.

    Attributes:
        bus: EventBus para publicação de eventos de recuperação.
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._bus = event_bus

    def attempt_restore(self, module: str, error: Exception) -> bool:
        """Tenta restaurar um módulo após falha.

        Args:
            module: Nome do módulo que falhou.
            error: Exceção que originou a falha.

        Returns:
            True se a recuperação foi iniciada com sucesso.
        """
        log.warning("Tentando recuperar modulo %s: %s", module, error)
        self._bus.publish(Event(EventTypes.RECOVERY_ATTEMPTED, {
            "module": module,
            "error": str(error),
        }))
        return True

    def rollback(self, module: str) -> None:
        """Executa rollback de um módulo para estado anterior.

        Args:
            module: Nome do módulo para reverter.
        """
        log.info("Executando rollback no modulo %s", module)
        self._bus.publish(Event(EventTypes.RECOVERY_ROLLBACK, {
            "module": module,
        }))
