"""
Interface abstrata para armazenamento de memória.

Permite diferentes backends de persistência (file, db, cloud).
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class MemoryStore(ABC):
    """Interface de armazenamento persistente para o sistema de memória."""

    @abstractmethod
    def save(self, collection: str, record_id: str, data: Dict[str, Any]) -> None:
        ...

    @abstractmethod
    def load(self, collection: str, record_id: str) -> Optional[Dict[str, Any]]:
        ...

    @abstractmethod
    def list_ids(self, collection: str) -> List[str]:
        ...

    @abstractmethod
    def delete(self, collection: str, record_id: str) -> None:
        ...

    @abstractmethod
    def count(self, collection: str) -> int:
        ...
