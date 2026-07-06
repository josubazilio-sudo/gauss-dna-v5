"""
Implementação file-based do MemoryStore.

Armazena cada registro como um arquivo JSON no disco.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .memory_store import MemoryStore

log = logging.getLogger(__name__)


class FileStore(MemoryStore):
    """Armazenamento baseado em arquivos JSON.

    Cada collection é uma pasta, cada registro é um arquivo .json.

    Attributes:
        root: Diretório raiz para armazenamento.
    """

    def __init__(self, root: Path) -> None:
        self._root = root
        root.mkdir(parents=True, exist_ok=True)

    def _collection_path(self, collection: str) -> Path:
        path = self._root / collection
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _file_path(self, collection: str, record_id: str) -> Path:
        return self._collection_path(collection) / f"{record_id}.json"

    def save(self, collection: str, record_id: str, data: Dict[str, Any]) -> None:
        path = self._file_path(collection, record_id)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            log.debug("Memoria salva: %s/%s", collection, record_id)
        except OSError as e:
            log.error("Falha ao salvar memoria %s/%s: %s", collection, record_id, e)
            raise

    def load(self, collection: str, record_id: str) -> Optional[Dict[str, Any]]:
        path = self._file_path(collection, record_id)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            log.error("Falha ao ler memoria %s/%s: %s", collection, record_id, e)
            return None

    def list_ids(self, collection: str) -> List[str]:
        path = self._collection_path(collection)
        return sorted(
            p.stem for p in path.iterdir() if p.suffix == ".json"
        )

    def delete(self, collection: str, record_id: str) -> None:
        path = self._file_path(collection, record_id)
        if path.exists():
            path.unlink()
            log.debug("Memoria removida: %s/%s", collection, record_id)

    def count(self, collection: str) -> int:
        return len(self.list_ids(collection))
