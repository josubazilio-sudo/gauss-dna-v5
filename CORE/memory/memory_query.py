"""
Sistema de consultas à memória.

Permite buscar, filtrar e analisar dados armazenados.
"""

import logging
from typing import Any, Callable, Dict, List, Optional

from .memory_store import MemoryStore

log = logging.getLogger(__name__)


class MemoryQuery:
    """Realiza consultas na memória persistente."""

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def find(self, collection: str, **filters: Any) -> List[Dict[str, Any]]:
        """Busca registros por campos exatos.

        Args:
            collection: Nome da coleção.
            **filters: Pares campo=valor para filtrar.

        Returns:
            Lista de registros que atendem aos filtros.
        """
        results = []
        for record_id in self._store.list_ids(collection):
            data = self._store.load(collection, record_id)
            if data is None:
                continue
            match = all(
                data.get(key) == value
                for key, value in filters.items()
            )
            if match:
                results.append(data)
        return results

    def search(self, collection: str, text: str, fields: List[str]) -> List[Dict[str, Any]]:
        """Busca textual em campos específicos.

        Args:
            collection: Nome da coleção.
            text: Texto para busca.
            fields: Lista de campos para procurar.

        Returns:
            Lista de registros que contêm o texto.
        """
        text_lower = text.lower()
        results = []
        for record_id in self._store.list_ids(collection):
            data = self._store.load(collection, record_id)
            if data is None:
                continue
            for field in fields:
                value = data.get(field, "")
                if isinstance(value, str) and text_lower in value.lower():
                    results.append(data)
                    break
        return results

    def aggregate(
        self,
        collection: str,
        key_fn: Callable[[Dict[str, Any]], Any],
    ) -> Dict[Any, int]:
        """Agrega contagem de registros por uma chave.

        Args:
            collection: Nome da coleção.
            key_fn: Função que extrai a chave de agregação.

        Returns:
            Dicionário chave -> contagem.
        """
        counts: Dict[Any, int] = {}
        for record_id in self._store.list_ids(collection):
            data = self._store.load(collection, record_id)
            if data is None:
                continue
            key = key_fn(data)
            counts[key] = counts.get(key, 0) + 1
        return counts
