"""
Sistema de busca textual no conhecimento.
"""

import logging
from typing import List, Optional

from .knowledge_entry import KnowledgeEntry, KnowledgeArea
from .knowledge_store import KnowledgeStore

log = logging.getLogger(__name__)


class KnowledgeSearch:
    """Busca entries de conhecimento por texto."""

    def __init__(self, store: KnowledgeStore) -> None:
        self._store = store

    def search(self, query: str, area: Optional[KnowledgeArea] = None) -> List[KnowledgeEntry]:
        """Busca entries que contenham o termo em título, conteúdo ou tags.

        Args:
            query: Termo de busca.
            area: Área para filtrar (opcional; busca todas se omitido).

        Returns:
            Lista de entries correspondentes, ordenados por relevância.
        """
        query_lower = query.lower()
        results: List[KnowledgeEntry] = []

        areas = [area] if area else list(KnowledgeArea)
        for a in areas:
            for entry in self._store.list_area(a):
                if self._matches(entry, query_lower):
                    results.append(entry)

        return results

    def _matches(self, entry: KnowledgeEntry, query_lower: str) -> bool:
        """Verifica se um entry corresponde ao termo de busca."""
        if query_lower in entry.title.lower():
            return True
        if query_lower in entry.content.lower():
            return True
        for tag in entry.tags:
            if query_lower in tag.lower():
                return True
        return False

    def search_by_tag(self, tag: str, area: Optional[KnowledgeArea] = None) -> List[KnowledgeEntry]:
        """Busca entries por tag exata."""
        tag_lower = tag.lower()
        results: List[KnowledgeEntry] = []
        areas = [area] if area else list(KnowledgeArea)
        for a in areas:
            for entry in self._store.list_area(a):
                if any(t.lower() == tag_lower for t in entry.tags):
                    results.append(entry)
        return results
