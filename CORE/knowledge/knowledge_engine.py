"""
Sistema de Conhecimento Oficial do QuantOS.

Base validada de conhecimento sobre mercado, trading,
risco, estatística, engenharia e inteligência artificial.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

from .knowledge_store import KnowledgeStore
from .file_knowledge_store import FileKnowledgeStore
from .knowledge_entry import KnowledgeEntry, KnowledgeArea
from .knowledge_registry import KnowledgeRegistry
from .knowledge_search import KnowledgeSearch
from .knowledge_validator import KnowledgeValidator
from .knowledge_report import KnowledgeReport

log = logging.getLogger(__name__)


class KnowledgeEngine:
    """Motor central do sistema de conhecimento.

    Usage:
        engine = KnowledgeEngine(base_dir=Path("KNOWLEDGE"))
        engine.add(KnowledgeEntry.create("market", "Titulo", "conteudo..."))
        results = engine.search("liquidez")
    """

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self._dir = base_dir or Path("KNOWLEDGE")
        self._store: KnowledgeStore = FileKnowledgeStore(self._dir)
        self._registry = KnowledgeRegistry()
        self._validator = KnowledgeValidator()
        self._search = KnowledgeSearch(self._store)
        self._report = KnowledgeReport(self._store, self._registry)

        log.info("Knowledge Engine inicializado: %s", self._dir)

    def add(self, entry: KnowledgeEntry) -> bool:
        """Adiciona um entry de conhecimento validado.

        Args:
            entry: Entry a ser adicionado.

        Returns:
            True se adicionado com sucesso.
        """
        errors = self._validator.validate(entry)
        if errors:
            for e in errors:
                log.error("Knowledge entry rejeitado: %s", e)
            return False
        self._store.save(entry)
        log.info(
            "Conhecimento registrado: [%s] %s (v%s)",
            entry.area.value, entry.title, entry.version,
        )
        return True

    def get(self, area: KnowledgeArea, entry_id: str) -> Optional[KnowledgeEntry]:
        """Recupera um entry pelo ID."""
        return self._store.load(area, entry_id)

    def list_area(self, area: KnowledgeArea) -> List[KnowledgeEntry]:
        """Lista entries de uma área."""
        return self._store.list_area(area)

    def search(self, query: str, area: Optional[KnowledgeArea] = None) -> List[KnowledgeEntry]:
        """Busca textual em todas as áreas ou em uma específica."""
        return self._search.search(query, area)

    def count(self, area: Optional[KnowledgeArea] = None) -> int:
        """Conta entries (total ou por área)."""
        if area:
            return len(self._store.list_area(area))
        return sum(len(self._store.list_area(a)) for a in KnowledgeArea)

    def report(self) -> str:
        """Gera relatório textual do conhecimento."""
        return self._report.generate()
