"""
Relatórios do sistema de conhecimento.
"""

import logging
from typing import Dict

from .knowledge_entry import KnowledgeArea, area_label
from .knowledge_store import KnowledgeStore
from .knowledge_registry import KnowledgeRegistry

log = logging.getLogger(__name__)


class KnowledgeReport:
    """Geração de relatórios do conhecimento."""

    def __init__(self, store: KnowledgeStore, registry: KnowledgeRegistry) -> None:
        self._store = store
        self._registry = registry

    def summary(self) -> Dict[str, int]:
        """Resumo quantitativo por área."""
        return {
            area.value: self._store.count(area)
            for area in KnowledgeArea
        }

    def generate(self) -> str:
        """Gera relatório textual completo."""
        summary = self.summary()
        total = sum(summary.values())
        lines = [
            "=== Base Oficial de Conhecimento ===\n",
            f"Total de entries: {total}\n",
        ]
        for area in KnowledgeArea:
            label = area_label(area)
            count = summary[area.value]
            categories = ", ".join(self._registry.categories(area))
            lines.append(f"\n[{label}] ({count} entries)")
            lines.append(f"  Categorias: {categories}")
            if count > 0:
                entries = self._store.list_area(area)
                for e in entries:
                    lines.append(f"    - {e.title} (v{e.version})")
        return "\n".join(lines)
