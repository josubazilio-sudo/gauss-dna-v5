"""
Configuração central do sistema de logging.

Chamar setup_logging() uma vez durante o bootstrap.
"""

import logging
import sys
from pathlib import Path
from typing import Optional

from .formatter import QuantOSFormatter
from .handlers import QuantOSConsoleHandler, QuantOSFileHandler


_initialized = False


def setup_logging(
    level: int = logging.INFO,
    log_dir: Optional[Path] = None,
    console: bool = True,
    file_log: bool = True,
) -> None:
    """Configura o sistema de logging global do QuantOS.

    Deve ser chamada uma única vez durante o bootstrap.

    Args:
        level: Nível mínimo de log (ex: logging.INFO, logging.DEBUG).
        log_dir: Diretório para logs em arquivo (opcional).
        console: Se True, adiciona handler de console.
        file_log: Se True e log_dir for fornecido, adiciona handler de arquivo.
    """
    global _initialized
    if _initialized:
        return

    root = logging.getLogger()
    root.setLevel(level)

    formatter = QuantOSFormatter()

    if console:
        console_handler = QuantOSConsoleHandler(level=level)
        console_handler.setFormatter(formatter)
        root.addHandler(console_handler)

    if file_log and log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_path = log_dir / "quantos.log"
        file_handler = QuantOSFileHandler(path=file_path, level=level)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    _initialized = True


def configure_logger(
    name: str,
    level: Optional[int] = None,
) -> logging.Logger:
    """Configura e retorna um logger específico.

    Útil para módulos que precisam de nível diferente do global.

    Args:
        name: Nome do logger (normalmente __name__).
        level: Nível específico (opcional; usa o nível global se omitido).

    Returns:
        logging.Logger configurado.
    """
    logger = logging.getLogger(name)
    if level is not None:
        logger.setLevel(level)
    return logger
