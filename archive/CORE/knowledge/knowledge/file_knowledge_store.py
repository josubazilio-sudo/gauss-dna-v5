"""
Implementação file-based do KnowledgeStore.

Cada área é uma pasta, cada entry é um arquivo JSON.
"""

import json
import logging
from pathlib import Path
from typing import List, Optional

from .knowledge_entry import KnowledgeEntry, KnowledgeArea
from .knowledge_store import KnowledgeStore

log = logging.getLogger(__name__)


class FileKnowledgeStore(KnowledgeStore):
    """Armazenamento de conhecimento em arquivos JSON.

    Attributes:
        root: Diretório raiz KNOWLEDGE/.
    """

    def __init__(self, root: Path) -> None:
        self._root = root
        root.mkdir(parents=True, exist_ok=True)

    def _area_path(self, area: KnowledgeArea) -> Path:
        path = self._root / area.value
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _file_path(self, area: KnowledgeArea, entry_id: str) -> Path:
        return self._area_path(area) / f"{entry_id}.json"

    def save(self, entry: KnowledgeEntry) -> None:
        path = self._file_path(entry.area, entry.entry_id)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(entry.to_dict(), f, indent=2, ensure_ascii=False, default=str)
            log.debug("Knowledge salvo: %s/%s", entry.area.value, entry.entry_id)
        except OSError as e:
            log.error("Falha ao salvar knowledge %s/%s: %s", entry.area.value, entry.entry_id, e)
            raise

    def load(self, area: KnowledgeArea, entry_id: str) -> Optional[KnowledgeEntry]:
        path = self._file_path(area, entry_id)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return KnowledgeEntry.from_dict(json.load(f))
        except (json.JSONDecodeError, OSError) as e:
            log.error("Falha ao ler knowledge %s/%s: %s", area.value, entry_id, e)
            return None

    def list_area(self, area: KnowledgeArea) -> List[KnowledgeEntry]:
        path = self._area_path(area)
        results = []
        for fpath in sorted(path.iterdir()):
            if fpath.suffix != ".json":
                continue
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    results.append(KnowledgeEntry.from_dict(json.load(f)))
            except (json.JSONDecodeError, OSError) as e:
                log.warning("Erro ao ler %s: %s", fpath.name, e)
        return results

    def delete(self, area: KnowledgeArea, entry_id: str) -> None:
        path = self._file_path(area, entry_id)
        if path.exists():
            path.unlink()
            log.debug("Knowledge removido: %s/%s", area.value, entry_id)

    def count(self, area: KnowledgeArea) -> int:
        path = self._area_path(area)
        return sum(1 for f in path.iterdir() if f.suffix == ".json")
