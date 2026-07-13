"""
Handlers globais de erro do QuantOS.

Registra exceções não tratadas e encaminha para o sistema de logging.
"""

import logging
import sys
import traceback
from typing import Type

from .exceptions import QuantOSError

log = logging.getLogger(__name__)


def global_exception_handler(
    exc_type: Type[BaseException],
    exc_value: BaseException,
    exc_tb: object,
) -> None:
    """Handler global para exceções não tratadas.

    Args:
        exc_type: Tipo da exceção.
        exc_value: Valor/instância da exceção.
        exc_tb: Traceback da exceção.
    """
    if issubclass(exc_type, QuantOSError):
        log.error("Excecao QuantOS: [%s] %s", exc_value.code, exc_value)
    elif issubclass(exc_type, KeyboardInterrupt):
        log.info("Sistema interrompido pelo usuario")
        sys.exit(0)
    else:
        log.critical("Excecao nao tratada: %s", exc_value)
        traceback.print_exception(exc_type, exc_value, exc_tb)


def setup_global_handlers() -> None:
    """Configura o handler global de exceções."""
    sys.excepthook = global_exception_handler
    log.debug("Handlers globais de erro configurados")
