"""
Interface de armazenamento para entries de conhecimento.
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from .knowledge_entry import KnowledgeEntry, KnowledgeArea


class KnowledgeStore(ABC):
    """Interface de persistência para o sistema de conhecimento."""

    @abstractmethod
    def save(self, entry: KnowledgeEntry) -> None:
        ...

    @abstractmethod
    def load(self, area: KnowledgeArea, entry_id: str) -> Optional[KnowledgeEntry]:
        ...

    @abstractmethod
    def list_area(self, area: KnowledgeArea) -> List[KnowledgeEntry]:
        ...

    @abstractmethod
    def delete(self, area: KnowledgeArea, entry_id: str) -> None:
        ...

    @abstractmethod
    def count(self, area: KnowledgeArea) -> int:
        ...
