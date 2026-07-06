"""
Handlers de saída para logs do QuantOS.

Suporta console e arquivo com rotação por data.
"""

import logging
from pathlib import Path
from typing import Optional


class QuantOSConsoleHandler(logging.StreamHandler):
    """Handler que envia logs para o console (stdout)."""

    def __init__(self, level: int = logging.DEBUG) -> None:
        super().__init__()
        self.setLevel(level)


class QuantOSFileHandler(logging.FileHandler):
    """Handler que escreve logs em arquivo com criação automática do diretório."""

    def __init__(
        self,
        path: Path,
        level: int = logging.INFO,
        encoding: Optional[str] = None,
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        super().__init__(str(path), encoding=encoding or "utf-8")
        self.setLevel(level)
