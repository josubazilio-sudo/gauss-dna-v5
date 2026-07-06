"""
Atualização programática do PROJECT_DNA.

Reflete mudanças significativas no arquivo PROJECT_DNA
para manter a memória do projeto sempre atualizada.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


class DNAUpdater:
    """Gerencia atualizações no PROJECT_DNA."""

    def __init__(self, dna_path: Optional[Path] = None) -> None:
        self._dna_path = dna_path or Path("docs/core/005_PROJECT_DNA.md")

    def append_section(self, title: str, content: str) -> None:
        """Adiciona uma nova seção de aprendizado ao PROJECT_DNA.

        Args:
            title: Título da seção.
            content: Conteúdo markdown da seção.
        """
        try:
            with open(self._dna_path, "a", encoding="utf-8") as f:
                f.write(f"\n### {title}\n\n")
                f.write(f"{content}\n")
                f.write(f"\n_Atualizado em: {datetime.now(timezone.utc).isoformat()}_\n")
            log.info("PROJECT_DNA atualizado: %s", title)
        except OSError as e:
            log.error("Falha ao atualizar PROJECT_DNA: %s", e)
            raise
