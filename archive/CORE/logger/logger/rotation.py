"""
Gerenciamento de rotação e retenção de logs.

Remove arquivos de log com mais de N dias.
"""

import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional

log = logging.getLogger(__name__)


class LogRotation:
    """Gerencia a limpeza de logs antigos.

    Attributes:
        log_dir: Diretório onde os logs são armazenados.
        max_days: Número máximo de dias para reter logs.
    """

    def __init__(self, log_dir: Path, max_days: int = 30) -> None:
        if max_days < 1:
            raise ValueError(f"max_days deve ser >= 1, recebido {max_days}")
        self._log_dir = log_dir
        self._max_days = max_days

    def rotate(self) -> None:
        """Remove arquivos de log mais antigos que max_days."""
        if not self._log_dir.exists():
            return

        cutoff = datetime.now(timezone.utc) - timedelta(days=self._max_days)
        removed = 0

        for path in self._log_dir.iterdir():
            if not path.is_file():
                continue
            try:
                mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
                if mtime < cutoff:
                    path.unlink()
                    removed += 1
            except OSError:
                log.warning("Nao foi possivel remover log antigo: %s", path)

        if removed:
            log.info("Rotacao concluida: %d arquivo(s) removido(s)", removed)

    def current_log_path(self, module: str) -> Path:
        """Retorna o caminho do arquivo de log para o módulo na data atual.

        Args:
            module: Nome do módulo (ex: 'bootstrap', 'engine').

        Returns:
            Path para o arquivo de log do dia.
        """
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self._log_dir.mkdir(parents=True, exist_ok=True)
        return self._log_dir / f"{module}_{date_str}.log"
