"""
Registro automático de mudanças no sistema.

Cada alteração relevante (config, código, baseline) gera
um entry imutável no histórico.
"""

import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .memory_store import MemoryStore

log = logging.getLogger(__name__)

_COLLECTION = "changes"


@dataclass
class ChangeEntry:
    """Registro de uma mudança no sistema.

    Attributes:
        change_id: Identificador único.
        change_type: Tipo (config, code, baseline, parameter, doc).
        module: Módulo afetado.
        description: Descrição da mudança.
        previous_value: Valor anterior (opcional).
        new_value: Novo valor (opcional).
        author: Responsável.
        version: Versão em que ocorreu.
        created_at: Timestamp UTC.
    """
    change_id: str
    change_type: str
    module: str
    description: str
    previous_value: str
    new_value: str
    author: str
    version: str
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def create(
        cls,
        change_type: str,
        module: str,
        description: str,
        previous_value: str = "",
        new_value: str = "",
        author: str = "system",
        version: str = "0.0.0",
    ) -> "ChangeEntry":
        return cls(
            change_id=uuid4().hex[:12],
            change_type=change_type,
            module=module,
            description=description,
            previous_value=previous_value,
            new_value=new_value,
            author=author,
            version=version,
            created_at=datetime.now(timezone.utc).isoformat(),
        )


class ChangeLog:
    """Gerencia o registro de mudanças."""

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def log(self, entry: ChangeEntry) -> None:
        self._store.save(_COLLECTION, entry.change_id, entry.to_dict())
        log.info("Mudanca registrada: %s [%s] %s", entry.change_id, entry.change_type, entry.description)

    def list_by_type(self, change_type: str) -> List[ChangeEntry]:
        all_changes = self._list_all()
        return [c for c in all_changes if c.change_type == change_type]

    def list_by_module(self, module: str) -> List[ChangeEntry]:
        all_changes = self._list_all()
        return [c for c in all_changes if c.module == module]

    def list_by_version(self, version: str) -> List[ChangeEntry]:
        all_changes = self._list_all()
        return [c for c in all_changes if c.version == version]

    def _list_all(self) -> List[ChangeEntry]:
        ids = self._store.list_ids(_COLLECTION)
        results = []
        for cid in ids:
            entry = self.get(cid)
            if entry:
                results.append(entry)
        return sorted(results, key=lambda x: x.created_at, reverse=True)

    def get(self, change_id: str) -> Optional[ChangeEntry]:
        data = self._store.load(_COLLECTION, change_id)
        if data is None:
            return None
        return ChangeEntry(**data)

    def count(self) -> int:
        return self._store.count(_COLLECTION)
