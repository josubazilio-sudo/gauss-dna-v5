"""
Formatador padronizado para logs do QuantOS.

Define o formato único de saída usado por toda a plataforma.
"""

import logging
from datetime import datetime, timezone
from typing import Optional


class QuantOSFormatter(logging.Formatter):
    """Formatador oficial do QuantOS.

    Formato: [YYYY-MM-DD HH:MM:SS] LEVEL    module    mensagem
    """

    FORMAT = "[%(asctime)s] %(levelname)-8s %(name)-20s %(message)s"
    DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

    def __init__(self) -> None:
        super().__init__(fmt=self.FORMAT, datefmt=self.DATE_FORMAT)

    def formatTime(self, record: logging.LogRecord, datefmt: Optional[str] = None) -> str:
        """Sobrescreve para usar timezone-aware UTC."""
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        return dt.strftime(datefmt or self.DATE_FORMAT)
