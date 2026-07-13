"""
Validação de entries de conhecimento.
"""

import logging
from typing import List

from .knowledge_entry import KnowledgeEntry

log = logging.getLogger(__name__)


class KnowledgeValidator:
    """Valida entries de conhecimento antes do registro."""

    MIN_TITLE_LENGTH = 3
    MIN_CONTENT_LENGTH = 10

    def validate(self, entry: KnowledgeEntry) -> List[str]:
        """Valida um entry completo.

        Args:
            entry: Entry a ser validado.

        Returns:
            Lista de erros (vazia se válido).
        """
        errors: List[str] = []
        if len(entry.title.strip()) < self.MIN_TITLE_LENGTH:
            errors.append(f"Titulo deve ter >= {self.MIN_TITLE_LENGTH} caracteres")
        if len(entry.content.strip()) < self.MIN_CONTENT_LENGTH:
            errors.append(f"Conteudo deve ter >= {self.MIN_CONTENT_LENGTH} caracteres")
        if not entry.area:
            errors.append("Area de conhecimento obrigatoria")
        return errors
