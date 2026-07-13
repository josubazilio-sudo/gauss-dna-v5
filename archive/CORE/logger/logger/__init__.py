"""
Sistema de logging centralizado do QuantOS.

Uso:
    import logging
    log = logging.getLogger(__name__)

    log.info("mensagem")
    log.error("erro", exc_info=True)

Configuração:
    from CORE.logger import setup_logging
    setup_logging(level=logging.INFO)
"""

from .log_levels import LogLevel
from .rotation import LogRotation
from .handlers import QuantOSFileHandler, QuantOSConsoleHandler
from .setup import setup_logging, configure_logger

__all__ = [
    "LogLevel",
    "LogRotation",
    "QuantOSFileHandler",
    "QuantOSConsoleHandler",
    "setup_logging",
    "configure_logger",
]
