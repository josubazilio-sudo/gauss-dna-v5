"""
Níveis oficiais de log do QuantOS.

Mapeia os níveis internos para os níveis do módulo logging padrão.
"""

from enum import Enum, auto
import logging


class LogLevel(Enum):
    """Níveis de severidade para logging."""

    DEBUG = auto()
    INFO = auto()
    WARNING = auto()
    ERROR = auto()
    CRITICAL = auto()


LEVEL_MAP = {
    LogLevel.DEBUG: logging.DEBUG,
    LogLevel.INFO: logging.INFO,
    LogLevel.WARNING: logging.WARNING,
    LogLevel.ERROR: logging.ERROR,
    LogLevel.CRITICAL: logging.CRITICAL,
}


def to_stdlib(level: LogLevel) -> int:
    """Converte LogLevel interno para constante do módulo logging.

    Args:
        level: Nível interno do QuantOS.

    Returns:
        Constante do módulo logging (ex: logging.INFO).
    """
    return LEVEL_MAP.get(level, logging.INFO)
